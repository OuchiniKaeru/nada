from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    attachment_ids: list[str] = []


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    content: str
