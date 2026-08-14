from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.chat import _sse
from app.models.session import Session
from app.models.message import Message
from app.schemas.squad import SquadCreate, SquadUpdate, SquadResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.squad_service import create_squad, get_squads, get_squad, update_squad, delete_squad
from app.services.session_service import get_or_create_session, create_message, first_user_message_map, session_display_title
from app.services.attachment_service import assign_attachments_to_message
from app.services.execution_service import record_execution
from app.runtime.agent_runtime import SquadChatRuntime

router = APIRouter()


@router.get("/squads", response_model=list[SquadResponse])
async def list_squads(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    squads = await get_squads(db, user.id)
    return [
        {
            "id": squad.id,
            "name": squad.name,
            "description": squad.description,
            "system_prompt": squad.system_prompt,
            "model_provider": squad.model_provider,
            "model_id": squad.model_id,
            "mode": squad.mode,
            "visibility": squad.visibility,
            "owner_id": squad.owner_id,
            "created_at": squad.created_at.isoformat() if getattr(squad, "created_at", None) else None,
            "updated_at": squad.updated_at.isoformat() if getattr(squad, "updated_at", None) else None,
            "leader_agent_id": getattr(squad, "leader_agent_id", None),
            "members": [
                {
                    "id": member.id,
                    "agent_id": member.agent_id,
                    "role": member.role,
                    "sort_order": member.sort_order,
                }
                for member in (squad.members or [])
            ],
            "tools_config": getattr(squad, "tools_config", None) or {},
            "workspace_config": getattr(squad, "workspace_config", None) or {},
            "skills_config": getattr(squad, "skills_config", None) or {},
            "mcp_tools_config": getattr(squad, "mcp_tools_config", None) or {},
            "icon": getattr(squad, "icon", None),
            "theme": getattr(squad, "theme", None),
        }
        for squad in squads
    ]


@router.get("/squads/{squad_id}", response_model=SquadResponse)
async def read_squad(squad_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    squad = await get_squad(db, user.id, squad_id)
    if not squad:
        raise HTTPException(status_code=404, detail="スクワッドが見つかりません。")
    return {
        "id": squad.id,
        "name": squad.name,
        "description": squad.description,
        "system_prompt": squad.system_prompt,
        "model_provider": squad.model_provider,
        "model_id": squad.model_id,
        "mode": squad.mode,
        "visibility": squad.visibility,
        "owner_id": squad.owner_id,
        "created_at": squad.created_at.isoformat() if getattr(squad, "created_at", None) else None,
        "updated_at": squad.updated_at.isoformat() if getattr(squad, "updated_at", None) else None,
        "leader_agent_id": getattr(squad, "leader_agent_id", None),
        "members": [
            {
                "id": member.id,
                "agent_id": member.agent_id,
                "role": member.role,
                "sort_order": member.sort_order,
            }
            for member in (squad.members or [])
        ],
        "tools_config": getattr(squad, "tools_config", None) or {},
        "workspace_config": getattr(squad, "workspace_config", None) or {},
        "skills_config": getattr(squad, "skills_config", None) or {},
        "mcp_tools_config": getattr(squad, "mcp_tools_config", None) or {},
        "icon": getattr(squad, "icon", None),
        "theme": getattr(squad, "theme", None),
    }


@router.post("/squads", response_model=SquadResponse)
async def create_squad_endpoint(data: SquadCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        squad = await create_squad(db, user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "id": squad.id,
        "name": squad.name,
        "description": squad.description,
        "system_prompt": squad.system_prompt,
        "model_provider": squad.model_provider,
        "model_id": squad.model_id,
        "mode": getattr(squad, "mode", "coordinate"),
        "visibility": squad.visibility,
        "owner_id": squad.owner_id,
        "created_at": getattr(squad, "created_at", None).isoformat() if getattr(squad, "created_at", None) else None,
        "updated_at": getattr(squad, "updated_at", None).isoformat() if getattr(squad, "updated_at", None) else None,
        "leader_agent_id": getattr(squad, "leader_agent_id", None),
        "members": [
            {
                "id": member.id,
                "agent_id": member.agent_id,
                "role": member.role,
                "sort_order": member.sort_order,
            }
            for member in (getattr(squad, "members", None) or [])
        ],
        "tools_config": getattr(squad, "tools_config", None) or {},
        "workspace_config": getattr(squad, "workspace_config", None) or {},
        "skills_config": getattr(squad, "skills_config", None) or {},
        "mcp_tools_config": getattr(squad, "mcp_tools_config", None) or {},
        "icon": getattr(squad, "icon", None),
        "theme": getattr(squad, "theme", None),
    }


@router.patch("/squads/{squad_id}", response_model=SquadResponse)
async def update_squad_endpoint(squad_id: str, data: SquadUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        squad = await update_squad(db, user.id, squad_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "id": squad.id,
        "name": squad.name,
        "description": squad.description,
        "system_prompt": squad.system_prompt,
        "model_provider": squad.model_provider,
        "model_id": squad.model_id,
        "mode": getattr(squad, "mode", "coordinate"),
        "visibility": squad.visibility,
        "owner_id": squad.owner_id,
        "created_at": getattr(squad, "created_at", None).isoformat() if getattr(squad, "created_at", None) else None,
        "updated_at": getattr(squad, "updated_at", None).isoformat() if getattr(squad, "updated_at", None) else None,
        "leader_agent_id": getattr(squad, "leader_agent_id", None),
        "members": [
            {
                "id": member.id,
                "agent_id": member.agent_id,
                "role": member.role,
                "sort_order": member.sort_order,
            }
            for member in (getattr(squad, "members", None) or [])
        ],
        "tools_config": getattr(squad, "tools_config", None) or {},
        "workspace_config": getattr(squad, "workspace_config", None) or {},
        "skills_config": getattr(squad, "skills_config", None) or {},
        "mcp_tools_config": getattr(squad, "mcp_tools_config", None) or {},
        "icon": getattr(squad, "icon", None),
        "theme": getattr(squad, "theme", None),
    }


@router.delete("/squads/{squad_id}")
async def delete_squad_endpoint(
    squad_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_squad(db, user.id, squad_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True}


@router.get("/squads/{squad_id}/sessions")
async def list_squad_sessions(squad_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    squad = await get_squad(db, user.id, squad_id)
    if not squad:
        raise HTTPException(status_code=404, detail="スクワッドが見つかりません。")

    result = await db.execute(
        select(Session)
        .where(
            Session.user_id == user.id,
            Session.squad_id == squad_id,
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
            "squad_id": session.squad_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }
        for session in sessions
    ]


@router.get("/squads/{squad_id}/sessions/{session_id}/messages")
async def list_squad_session_messages(
    squad_id: str,
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    squad = await get_squad(db, user.id, squad_id)
    if not squad:
        raise HTTPException(status_code=404, detail="スクワッドが見つかりません。")
    session = await db.get(Session, session_id)
    if not session or session.squad_id != squad_id or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="セッションが見つかりません。")

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


@router.post("/squads/{squad_id}/chat")
async def chat_with_squad(
    squad_id: str,
    payload: ChatRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    squad = await get_squad(db, user.id, squad_id)
    if not squad:
        raise HTTPException(status_code=404, detail="スクワッドが見つかりません。")

    session = await get_or_create_session(db, user.id, agent_id=None, squad_id=squad_id, title="New Squad Chat")
    user_message = await create_message(db, session.id, payload.message, role="user")

    if payload.attachment_ids:
        await assign_attachments_to_message(db, user_message.id, payload.attachment_ids)

    runtime = SquadChatRuntime(squad, db, session.id)

    async def stream():
        parts: list[str] = []
        async for chunk in runtime.astream(payload.message, payload.attachment_ids):
            parts.append(chunk)
            yield _sse({"type": "delta", "content": chunk})
        full = "".join(parts).strip() or "(no response)"
        assistant_message = await create_message(db, session.id, full, role="assistant")
        await record_execution(
            db,
            user_id=str(user.id),
            agent_id=getattr(squad, "leader_agent_id", None) or "",
            session_id=session.id,
            squad_id=squad.id,
            model=squad.model_id,
            usage=runtime.usage,
        )
        yield _sse({
            "type": "done",
            "session_id": session.id,
            "message_id": assistant_message.id,
            "content": full,
        })

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
