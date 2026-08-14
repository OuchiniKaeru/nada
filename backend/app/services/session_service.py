import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.models.message import Message

logger = logging.getLogger(__name__)


async def create_session(
    db: AsyncSession,
    user_id: str,
    agent_id: str | None = None,
    squad_id: str | None = None,
    title: str = "New Chat",
) -> Session:
    session = Session(
        id=str(uuid.uuid4()),
        user_id=user_id,
        agent_id=agent_id or "",
        squad_id=squad_id,
        title=title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_or_create_session(
    db: AsyncSession,
    user_id: str,
    agent_id: str | None = None,
    session_id: str | None = None,
    squad_id: str | None = None,
    title: str = "New Chat",
) -> Session:
    if session_id:
        session = await db.get(Session, session_id)
        if session:
            return session
    return await create_session(db, user_id, agent_id=agent_id, squad_id=squad_id, title=title)


async def create_message(
    db: AsyncSession,
    session_id: str,
    content: str,
    role: str = "user",
    sequence: int | None = None,
) -> Message:
    try:
        if sequence is None:
            result = await db.execute(
                select(Message.sequence)
                .where(Message.session_id == session_id)
                .order_by(Message.sequence.desc())
                .limit(1)
            )
            last_sequence = result.scalar_one_or_none()
            sequence = (last_sequence or 0) + 1

        message = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            content=content,
            role=role,
            sequence=sequence,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("create_message failed for session=%s role=%s sequence=%s", session_id, role, sequence)
        raise
    return message


async def get_session_messages(db: AsyncSession, session_id: str) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.sequence.asc(), Message.created_at.asc())
    )
    return list(result.scalars().all())


GENERIC_TITLES = {"new chat", "new squad chat", ""}


async def first_user_message_map(db: AsyncSession, session_ids: list[str]) -> dict[str, str]:
    """First user-message text per session (for deriving display titles)."""
    if not session_ids:
        return {}
    result = await db.execute(
        select(Message.session_id, Message.content)
        .where(Message.session_id.in_(session_ids), Message.role == "user")
        .order_by(Message.sequence.asc())
    )
    first: dict[str, str] = {}
    for sid, content in result.all():
        if sid not in first:
            first[sid] = (content or "").strip()
    return first


def session_display_title(title: str | None, first_user_message: str | None) -> str:
    """Resolve a sidebar label: real title → first 20 chars of first msg → default."""
    t = (title or "").strip()
    if t and t.lower() not in GENERIC_TITLES:
        return t
    msg = (first_user_message or "").strip()
    if msg:
        return msg[:20] + ("…" if len(msg) > 20 else "")
    return "New Chat"
