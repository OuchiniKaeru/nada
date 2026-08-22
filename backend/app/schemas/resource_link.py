from typing import Any, Optional

from pydantic import BaseModel


class ResourceLinkEntry(BaseModel):
    resource_id: str
    enabled: bool = True


class ResourceLinksUpdate(BaseModel):
    links: list[ResourceLinkEntry]


class ResourceLinksResponse(BaseModel):
    parent_type: str
    parent_id: str
    links: list[ResourceLinkEntry]

    model_config = {"from_attributes": True}


class ResourceConfigValidateRequest(BaseModel):
    config_format: str
    config_text: str


class ResourceConfigValidateResponse(BaseModel):
    ok: bool
    error: Optional[str] = None


class EnabledResourcesResponse(BaseModel):
    parent_type: str
    parent_id: str
    resources: dict[str, list[dict[str, Any]]]
