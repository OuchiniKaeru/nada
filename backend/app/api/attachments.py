from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.services.attachment_service import save_attachment

router = APIRouter()

@router.post("/attachments")
async def upload_attachment(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    attachment = await save_attachment(db, file.filename, content, file.content_type or "application/octet-stream", user.id)
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "url": f"/uploads/{attachment.id}",
    }
