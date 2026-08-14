from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate
from app.services.agent_service import create_agent, get_agents, get_agent, update_agent, delete_agent


router = APIRouter()


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agents = await get_agents(db, user.id)
    return [
        {
            "id": agent.id,
            "title": agent.title,
            "description": agent.description,
            "system_prompt": agent.system_prompt,
            "model_provider": agent.model_provider,
            "model_id": agent.model_id,
            "visibility": agent.visibility.value if hasattr(agent.visibility, "value") else agent.visibility,
            "ad_group": agent.ad_group,
            "skill_ids": agent.skill_ids or [],
            "mcp_server_id": agent.mcp_server_id,
            "mcp_server_ids": agent.mcp_server_ids or [],
            "tools_config": agent.tools_config or {},
            "workspace_config": agent.workspace_config or {},
            "skills_config": agent.skills_config or {},
            "mcp_tools_config": agent.mcp_tools_config or {},
            "icon": agent.icon,
            "theme": agent.theme,
            "status": agent.status,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }
        for agent in agents
    ]


@router.post("/agents", response_model=AgentResponse)
async def create_agent_endpoint(
    data: AgentCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await create_agent(db, user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def read_agent(
    agent_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = await get_agent(db, user.id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="エージェントが見つかりません。")
    return agent


@router.patch("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent_endpoint(
    agent_id: str,
    data: AgentUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_agent(db, user.id, agent_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/agents/{agent_id}")
async def delete_agent_endpoint(
    agent_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_agent(db, user.id, agent_id)
    return {"status": "deleted"}
