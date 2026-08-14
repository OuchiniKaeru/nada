import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.agent import Agent
from app.models.squad import Squad
from app.models.squad_member import SquadMember
from app.models.session import Session
from app.schemas.squad import SquadCreate, SquadUpdate


async def create_squad(db: AsyncSession, user_id: str, data: SquadCreate) -> Squad:
    candidate_ids = list(dict.fromkeys([*(data.team_agent_ids or []), *(data.leader_agent_id and [data.leader_agent_id] or [])]))
    valid_agent_ids = set()
    if candidate_ids:
        result = await db.execute(
            select(Agent.id).where(Agent.id.in_(candidate_ids), Agent.owner_id == user_id)
        )
        valid_agent_ids = {row[0] for row in result.all()}
        invalid_ids = [agent_id for agent_id in candidate_ids if agent_id not in valid_agent_ids]
        if invalid_ids:
            raise ValueError("選択されたエージェントの一部が存在しないか、アクセスできません。")

    squad = Squad(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        model_provider=data.model_provider,
        model_id=data.model_id,
        visibility=data.visibility,
        owner_id=user_id,
        leader_agent_id=data.leader_agent_id,
        tools_config=data.tools_config or {},
        workspace_config=data.workspace_config or {},
        skills_config=data.skills_config or {},
        mcp_tools_config=data.mcp_tools_config or {},
        icon=data.icon,
        theme=data.theme or "dark-emerald",
    )
    db.add(squad)
    await db.commit()
    await db.refresh(squad)

    members = []
    if data.leader_agent_id and data.leader_agent_id in valid_agent_ids:
        members.append(
            SquadMember(
                id=str(uuid.uuid4()),
                squad_id=squad.id,
                agent_id=data.leader_agent_id,
                role="leader",
                sort_order=0,
            )
        )
    for index, agent_id in enumerate((data.team_agent_ids or []), start=1):
        if agent_id not in valid_agent_ids:
            continue
        members.append(
            SquadMember(
                id=str(uuid.uuid4()),
                squad_id=squad.id,
                agent_id=agent_id,
                role="member",
                sort_order=index,
            )
        )
    for member in members:
        db.add(member)
    await db.commit()
    await db.refresh(squad)
    squad.members = members
    return squad


async def get_squads(db: AsyncSession, owner_id: str) -> list[Squad]:
    result = await db.execute(
        select(Squad).where(Squad.owner_id == owner_id).order_by(Squad.created_at.desc())
    )
    squads = list(result.scalars().all())

    for squad in squads:
        member_result = await db.execute(
            select(SquadMember).where(SquadMember.squad_id == squad.id).order_by(SquadMember.sort_order.asc())
        )
        squad.members = list(member_result.scalars().all())

    return squads


async def get_squad(db: AsyncSession, owner_id: str, squad_id: str) -> Squad | None:
    squad = await db.get(Squad, squad_id)
    if not squad or squad.owner_id != owner_id:
        return None

    member_result = await db.execute(
        select(SquadMember).where(SquadMember.squad_id == squad.id).order_by(SquadMember.sort_order.asc())
    )
    squad.members = list(member_result.scalars().all())
    return squad


async def update_squad(db: AsyncSession, owner_id: str, squad_id: str, data: SquadCreate | SquadUpdate) -> Squad:
    squad = await get_squad(db, owner_id, squad_id)
    if not squad:
        raise ValueError("スクワッドが見つかりません。")

    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data:
        squad.name = update_data["name"]
    if "description" in update_data:
        squad.description = update_data["description"]
    if "system_prompt" in update_data:
        squad.system_prompt = update_data["system_prompt"]
    if "model_provider" in update_data:
        squad.model_provider = update_data["model_provider"]
    if "model_id" in update_data:
        squad.model_id = update_data["model_id"]
    if "visibility" in update_data:
        squad.visibility = update_data["visibility"]
    if "leader_agent_id" in update_data:
        squad.leader_agent_id = update_data["leader_agent_id"]

    for key, value in update_data.items():
        if key in {"tools_config", "workspace_config", "skills_config", "mcp_tools_config"} and value is None:
            value = {}
        setattr(squad, key, value)

    candidate_ids = list(dict.fromkeys([*(update_data.get("team_agent_ids") or []), *(update_data.get("leader_agent_id") and [update_data["leader_agent_id"]] or [])]))
    valid_agent_ids = set()
    if candidate_ids:
        result = await db.execute(
            select(Agent.id).where(Agent.id.in_(candidate_ids), Agent.owner_id == owner_id)
        )
        valid_agent_ids = {row[0] for row in result.all()}
        invalid_ids = [agent_id for agent_id in candidate_ids if agent_id not in valid_agent_ids]
        if invalid_ids:
            raise ValueError("選択されたエージェントの一部が存在しないか、アクセスできません。")

    old_members_result = await db.execute(
        select(SquadMember).where(SquadMember.squad_id == squad.id)
    )
    old_members = list(old_members_result.scalars().all())
    for old_member in old_members:
        await db.delete(old_member)
    await db.flush()

    new_members = []
    if update_data.get("leader_agent_id") and update_data["leader_agent_id"] in valid_agent_ids:
        new_members.append(
            SquadMember(
                id=str(uuid.uuid4()),
                squad_id=squad.id,
                agent_id=update_data["leader_agent_id"],
                role="leader",
                sort_order=0,
            )
        )
    for index, agent_id in enumerate((update_data.get("team_agent_ids") or []), start=1):
        if agent_id not in valid_agent_ids:
            continue
        if agent_id == update_data.get("leader_agent_id"):
            continue
        new_members.append(
            SquadMember(
                id=str(uuid.uuid4()),
                squad_id=squad.id,
                agent_id=agent_id,
                role="member",
                sort_order=index,
            )
        )
    for member in new_members:
        db.add(member)

    await db.commit()
    await db.refresh(squad)
    squad.members = new_members
    return squad


async def delete_squad(db: AsyncSession, owner_id: str, squad_id: str) -> None:
    squad = await get_squad(db, owner_id, squad_id)
    if not squad:
        raise ValueError("スクワッドが見つかりません。")

    member_result = await db.execute(
        select(SquadMember).where(SquadMember.squad_id == squad.id)
    )
    for member in member_result.scalars().all():
        await db.delete(member)

    session_result = await db.execute(
        select(Session).where(Session.squad_id == squad.id)
    )
    for session in session_result.scalars().all():
        await db.delete(session)

    await db.delete(squad)
    await db.commit()
