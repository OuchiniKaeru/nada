import logging
import uuid
import asyncio
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.session import Session
from app.models.message import Message
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.session_service import get_or_create_session, create_message, first_user_message_map, session_display_title
from app.services.attachment_service import assign_attachments_to_message
from app.services.execution_service import record_execution
from app.runtime.agent_runtime import AgentRuntime, SquadChatRuntime

router = APIRouter()
logger = logging.getLogger(__name__)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _save_message(db: AsyncSession, session_id: str, content: str, role: str) -> Message:
    try:
        return await create_message(db, session_id, content, role=role)
    except asyncio.CancelledError:
        # Distinguish a real request cancellation from a leaked CancelledError.
        # agno's MCP client tears down anyio cancel scopes inside its run, which
        # can inject a spurious CancelledError into the *request* task at the
        # next await (the DB commit here) even though uvicorn never cancelled the
        # request — the client still receives a response. Task.cancelling() == 0
        # tells us the task is NOT actually being cancelled. In that case we
        # roll back the interrupted transaction (nothing committed yet) and retry
        # once, so the message still saves and we don't turn a successful MCP run
        # into a 500.
        task = asyncio.current_task()
        if task is not None and task.cancelling() == 0:
            logger.warning(
                "[chat] leaked CancelledError during create_message role=%s session=%s — retrying",
                role, session_id,
            )
            try:
                await db.rollback()
            except Exception:
                pass
            try:
                return await create_message(db, session_id, content, role=role)
            except asyncio.CancelledError:
                logger.error("[chat] create_message cancelled again role=%s session=%s", role, session_id)
                raise HTTPException(status_code=500, detail="メッセージの保存に失敗しました。")
            except Exception as exc:
                logger.exception("chat_with_agent failed at create_message role=%s: %s", role, exc)
                raise HTTPException(status_code=500, detail="メッセージの保存に失敗しました。")
        logger.error("[chat] create_message cancelled role=%s session=%s", role, session_id)
        raise HTTPException(status_code=500, detail="メッセージの保存に失敗しました。")
    except Exception as exc:
        logger.exception("chat_with_agent failed at create_message role=%s: %s", role, exc)
        raise HTTPException(status_code=500, detail="メッセージの保存に失敗しました。")


@router.post("/agents/{agent_id}/chat")
async def chat_with_agent(
    agent_id: str,
    payload: ChatRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info("[chat] start agent=%s user=%s", agent_id, user.id)
    session = await get_or_create_session(db, user.id, agent_id, payload.session_id)
    logger.info("[chat] session ready=%s", session.id)
    user_message = await _save_message(db, session.id, payload.message, role="user")
    logger.info("[chat] user message saved=%s", getattr(user_message, "id", None))

    if payload.attachment_ids:
        await assign_attachments_to_message(db, user_message.id, payload.attachment_ids)

    runtime = AgentRuntime(agent_id, db, session_id=session.id, user_id=str(user.id))

    async def stream():
        parts: list[str] = []
        async for chunk in runtime.astream(payload.message, payload.attachment_ids):
            parts.append(chunk)
            yield _sse({"type": "delta", "content": chunk})
        full = "".join(parts).strip() or "(no response)"
        logger.info("[chat] runtime done len=%s", len(full))
        assistant_message = await _save_message(db, session.id, full, role="assistant")
        await record_execution(
            db,
            user_id=str(user.id),
            agent_id=agent_id,
            session_id=session.id,
            model=runtime.usage.get("model", ""),
            usage=runtime.usage,
        )
        yield _sse({
            "type": "done",
            "session_id": session.id,
            "message_id": assistant_message.id,
            "content": full,
        })

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@router.get("/agents/{agent_id}/sessions")
async def list_agent_sessions(
    agent_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session)
        .where(
            Session.user_id == user.id,
            Session.agent_id == agent_id,
            Session.updated_at >= datetime.utcnow() - timedelta(days=7),
        )
        .order_by(Session.updated_at.desc())
    )
    sessions = result.scalars().all()
    first_msgs = await first_user_message_map(db, [s.id for s in sessions])
    return [
        {
            "id": session.id,
            "title": session_display_title(session.title, first_msgs.get(session.id)),
            "agent_id": session.agent_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }
        for session in sessions
    ]


@router.get("/agents/{agent_id}/sessions/{session_id}/messages")
async def list_session_messages(
    agent_id: str,
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session or session.agent_id != agent_id or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="セッションが見つかりません。")

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.sequence.asc(), Message.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        {
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "sequence": message.sequence,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        }
        for message in messages
    ]
