import uuid
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.attachment import Attachment

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

async def save_attachment(
    db: AsyncSession,
    file_name: str,
    content: bytes,
    content_type: str,
    user_id: str,
    message_id: str | None = None,
) -> Attachment:
    file_id = str(uuid.uuid4())
    saved_name = f"{file_id}-{file_name}"
    file_path = UPLOAD_DIR / saved_name
    file_path.write_bytes(content)
    attachment = Attachment(
        id=file_id,
        message_id=message_id or "",
        filename=file_name,
        content_type=content_type,
        file_path=str(file_path),
        size=len(content),
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


async def list_attachments_by_ids(db: AsyncSession, attachment_ids: list[str] | None) -> list[Attachment]:
    """Load attachment rows by ids (ordered, safe for empty input)."""
    if not attachment_ids:
        return []
    result = await db.execute(select(Attachment).where(Attachment.id.in_(attachment_ids)))
    by_id = {att.id: att for att in result.scalars().all()}
    return [by_id[a_id] for a_id in attachment_ids if a_id in by_id]


async def assign_attachments_to_message(db: AsyncSession, message_id: str, attachment_ids: list[str]) -> None:
    if not attachment_ids:
        return

    result = await db.execute(select(Attachment).where(Attachment.id.in_(attachment_ids)))
    attachments = result.scalars().all()
    for attachment in attachments:
        attachment.message_id = message_id
    await db.commit()
