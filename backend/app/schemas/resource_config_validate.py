from pydantic import BaseModel
from typing import Optional


class ResourceConfigValidateRequest(BaseModel):
    config_format: str
    config_text: str


class ResourceConfigValidateResponse(BaseModel):
    ok: bool
    error: Optional[str] = None
