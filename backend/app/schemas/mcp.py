from pydantic import BaseModel, ConfigDict
from typing import Optional


class MCPCreate(BaseModel):
    name: str
    description: str
    url: Optional[str] = None
    transport: Optional[str] = None
    auth_type: Optional[str] = None
    auth_secret: Optional[str] = None
    enabled: bool = True
    config: Optional[dict] = None
    icon: str | None = None
    theme: str | None = None


class MCPUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    transport: Optional[str] = None
    auth_type: Optional[str] = None
    auth_secret: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[dict] = None
    icon: str | None = None
    theme: str | None = None


class MCPResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    url: Optional[str] = None
    transport: Optional[str] = None
    auth_type: Optional[str] = None
    enabled: bool
    config: Optional[dict] = None
    icon: str | None = None
    theme: str | None = None
