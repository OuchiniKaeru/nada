from pydantic import BaseModel, ConfigDict
from typing import Optional


class SkillCreate(BaseModel):
    name: str
    description: str
    content: str
    visibility: str = "private"
    icon: str | None = None
    theme: str | None = None


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    visibility: Optional[str] = None
    icon: str | None = None
    theme: str | None = None


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    content: str
    visibility: str
    icon: str | None = None
    theme: str | None = None
