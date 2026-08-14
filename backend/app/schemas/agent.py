from pydantic import BaseModel, ConfigDict
from app.models.agent import Visibility


class AgentCreate(BaseModel):
    title: str
    description: str
    system_prompt: str
    model_provider: str
    model_id: str
    visibility: Visibility = Visibility.private
    ad_group: str | None = None
    skill_ids: list[str] = []
    mcp_server_id: str | None = None
    mcp_server_ids: list[str] = []
    tools_config: dict | None = None
    workspace_config: dict | None = None
    skills_config: dict | None = None
    mcp_tools_config: dict | None = None
    icon: str | None = None
    theme: str | None = None


class AgentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model_provider: str | None = None
    model_id: str | None = None
    visibility: Visibility | None = None
    ad_group: str | None = None
    skill_ids: list[str] | None = None
    mcp_server_id: str | None = None
    mcp_server_ids: list[str] | None = None
    tools_config: dict | None = None
    workspace_config: dict | None = None
    skills_config: dict | None = None
    mcp_tools_config: dict | None = None
    icon: str | None = None
    theme: str | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    system_prompt: str
    model_provider: str
    model_id: str
    visibility: Visibility
    ad_group: str | None = None
    skill_ids: list[str] = []
    mcp_server_id: str | None = None
    mcp_server_ids: list[str] = []
    tools_config: dict | None = None
    workspace_config: dict | None = None
    skills_config: dict | None = None
    mcp_tools_config: dict | None = None
    icon: str | None = None
    theme: str | None = None
