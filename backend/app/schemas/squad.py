from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class SquadCreate(BaseModel):
    name: str
    description: str
    system_prompt: str
    model_provider: str
    model_id: str
    leader_agent_id: Optional[str] = None
    team_agent_ids: List[str] = []
    visibility: str = "private"
    tools_config: dict | None = None
    workspace_config: dict | None = None
    skills_config: dict | None = None
    mcp_tools_config: dict | None = None
    icon: str | None = None
    theme: str | None = None


class SquadUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model_provider: Optional[str] = None
    model_id: Optional[str] = None
    leader_agent_id: Optional[str] = None
    team_agent_ids: List[str] = []
    visibility: Optional[str] = None
    tools_config: dict | None = None
    workspace_config: dict | None = None
    skills_config: dict | None = None
    mcp_tools_config: dict | None = None
    icon: str | None = None
    theme: str | None = None


class SquadMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    role: str
    sort_order: int


class SquadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    system_prompt: str
    model_provider: str
    model_id: str
    mode: str
    visibility: str
    owner_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    leader_agent_id: Optional[str] = None
    members: List[SquadMemberResponse] = []
    tools_config: dict | None = None
    workspace_config: dict | None = None
    skills_config: dict | None = None
    mcp_tools_config: dict | None = None
    icon: str | None = None
    theme: str | None = None
