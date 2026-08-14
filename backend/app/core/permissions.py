from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, Visibility
from app.models.user import User


async def can_access_agent(db: AsyncSession, user: User, agent_id: str) -> bool:
    result = await db.get(Agent, agent_id)
    if result is None:
        return False

    if result.visibility == Visibility.public:
        return True
    if result.owner_id == user.id:
        return True
    if result.visibility == Visibility.ad_group:
        return False

    return False
