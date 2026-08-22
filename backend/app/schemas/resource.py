from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ResourceType = Literal["model", "system_prompt", "rule", "skill", "mcp", "tool", "hook", "loop"]
ConfigFormat = Literal["json", "yaml", "python", "markdown"]


class ResourceCreate(BaseModel):
    type: ResourceType
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    visibility: str = "private"
    config_format: ConfigFormat = "json"
    config_text: str = ""


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    config_format: Optional[ConfigFormat] = None
    config_text: Optional[str] = None


class ResourceResponse(BaseModel):
    id: str
    type: str
    name: str
    description: str
    visibility: str
    config_format: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResourceConfigResponse(BaseModel):
    resource_id: str
    config_format: str
    config_text: str
