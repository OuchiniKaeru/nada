from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.mcp import MCPServer
from app.models.skill import Skill
from app.schemas.agent import AgentCreate, AgentUpdate

import uuid


async def _validate_mcp_and_skills(
    db: AsyncSession,
    owner_id: str,
    mcp_server_ids: list[str] | None,
    skill_ids: list[str],
) -> None:
    if mcp_server_ids:
        for mcp_server_id in mcp_server_ids:
            mcp = await db.get(MCPServer, mcp_server_id)
            if not mcp or mcp.owner_id != owner_id:
                raise ValueError("選択されたMCPサーバーが存在しないか、アクセスできません。")
            if not mcp.enabled:
                raise ValueError("選択されたMCPサーバーは無効です。")

    if skill_ids:
        result = await db.execute(
            select(Skill.id).where(Skill.id.in_(skill_ids), Skill.owner_id == owner_id)
        )
        found_ids = {row[0] for row in result.all()}
        missing = [skill_id for skill_id in skill_ids if skill_id not in found_ids]
        if missing:
            raise ValueError("選択されたSkillの一部が存在しないか、アクセスできません。")


async def create_agent(
    db: AsyncSession,
    user_id: str,
    data: AgentCreate,
) -> Agent:
    await _validate_mcp_and_skills(db, user_id, data.mcp_server_ids or [], data.skill_ids or [])

    agent = Agent(
        id=str(uuid.uuid4()),
        title=data.title,
        description=data.description,
        system_prompt=data.system_prompt,
        model_provider=data.model_provider,
        model_id=data.model_id,
        visibility=data.visibility,
        ad_group=data.ad_group,
        mcp_server_id=data.mcp_server_id,
        mcp_server_ids=data.mcp_server_ids or [],
        skill_ids=data.skill_ids or [],
        tools_config=data.tools_config or {},
        workspace_config=data.workspace_config or {},
        skills_config=data.skills_config or {},
        mcp_tools_config=data.mcp_tools_config or {},
        icon=data.icon,
        theme=data.theme or "dark-emerald",
        owner_id=user_id,
    )

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return agent


async def get_agents(
    db: AsyncSession,
    owner_id: str,
) -> list[Agent]:
    result = await db.execute(
        select(Agent)
        .where(Agent.owner_id == owner_id)
        .order_by(Agent.created_at.desc())
    )

    return list(result.scalars().all())


async def get_agent(
    db: AsyncSession,
    owner_id: str,
    agent_id: str,
) -> Agent | None:
    agent = await db.get(Agent, agent_id)
    if agent and agent.owner_id == owner_id:
        return agent
    return None


async def update_agent(
    db: AsyncSession,
    owner_id: str,
    agent_id: str,
    data: AgentUpdate,
) -> Agent:
    agent = await get_agent(db, owner_id, agent_id)
    if not agent:
        raise ValueError("エージェントが見つかりません。")

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return agent

    mcp_server_ids = updates.get("mcp_server_ids", agent.mcp_server_ids or [])
    skill_ids = updates.get("skill_ids", agent.skill_ids or [])
    await _validate_mcp_and_skills(db, owner_id, mcp_server_ids, skill_ids)

    for key, value in updates.items():
        if key in {"tools_config", "workspace_config", "skills_config", "mcp_tools_config"} and value is None:
            value = {}
        setattr(agent, key, value)

    await db.commit()
    await db.refresh(agent)
    return agent


async def delete_agent(
    db: AsyncSession,
    owner_id: str,
    agent_id: str,
) -> None:
    agent = await get_agent(db, owner_id, agent_id)
    if not agent:
        raise ValueError("エージェントが見つかりません。")
    await db.delete(agent)
    await db.commit()
