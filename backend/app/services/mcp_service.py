import uuid
import json
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.mcp import MCPServer
from app.schemas.mcp import MCPCreate, MCPUpdate


async def create_mcp(db: AsyncSession, user_id: str, data: MCPCreate) -> MCPServer:
    mcp = MCPServer(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        url=data.url,
        transport=data.transport,
        auth_type=data.auth_type,
        auth_secret_encrypted=data.auth_secret,
        enabled=data.enabled,
        config=data.config,
        owner_id=user_id,
        icon=data.icon,
        theme=data.theme or "dark-emerald",
    )
    db.add(mcp)
    await db.commit()
    await db.refresh(mcp)
    return mcp


async def get_mcps(db: AsyncSession, owner_id: str) -> list[MCPServer]:
    result = await db.execute(
        select(MCPServer).where(MCPServer.owner_id == owner_id).order_by(MCPServer.created_at.desc())
    )
    return list(result.scalars().all())


async def update_mcp(db: AsyncSession, user_id: str, mcp_id: str, data: MCPUpdate) -> MCPServer | None:
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == mcp_id, MCPServer.owner_id == user_id)
    )
    mcp = result.scalar_one_or_none()
    if not mcp:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data:
        mcp.name = update_data["name"]
    if "description" in update_data:
        mcp.description = update_data["description"]
    if "url" in update_data:
        mcp.url = update_data["url"]
    if "transport" in update_data:
        mcp.transport = update_data["transport"]
    if "auth_type" in update_data:
        mcp.auth_type = update_data["auth_type"]
    if "auth_secret" in update_data and update_data["auth_secret"] is not None:
        mcp.auth_secret_encrypted = update_data["auth_secret"]
    if "enabled" in update_data:
        mcp.enabled = update_data["enabled"]
    if "config" in update_data:
        mcp.config = update_data["config"]
    if "icon" in update_data:
        mcp.icon = update_data["icon"]
    if "theme" in update_data:
        mcp.theme = update_data["theme"]

    await db.commit()
    await db.refresh(mcp)
    return mcp


async def delete_mcp(db: AsyncSession, user_id: str, mcp_id: str) -> MCPServer | None:
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == mcp_id, MCPServer.owner_id == user_id)
    )
    mcp = result.scalar_one_or_none()
    if not mcp:
        return None

    await db.delete(mcp)
    await db.commit()
    return mcp
