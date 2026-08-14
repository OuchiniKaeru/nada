import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.skill import Skill
from app.schemas.skill import SkillCreate, SkillUpdate


async def create_skill(db: AsyncSession, user_id: str, data: SkillCreate) -> Skill:
    skill = Skill(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        content=data.content,
        visibility=data.visibility,
        owner_id=user_id,
        icon=data.icon,
        theme=data.theme or "dark-emerald",
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


async def get_skills(db: AsyncSession, owner_id: str) -> list[Skill]:
    result = await db.execute(
        select(Skill).where(Skill.owner_id == owner_id).order_by(Skill.created_at.desc())
    )
    return list(result.scalars().all())


async def update_skill(db: AsyncSession, user_id: str, skill_id: str, data: SkillUpdate) -> Skill | None:
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.owner_id == user_id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data:
        skill.name = update_data["name"]
    if "description" in update_data:
        skill.description = update_data["description"]
    if "content" in update_data:
        skill.content = update_data["content"]
    if "visibility" in update_data:
        skill.visibility = update_data["visibility"]
    if "icon" in update_data:
        skill.icon = update_data["icon"]
    if "theme" in update_data:
        skill.theme = update_data["theme"]

    await db.commit()
    await db.refresh(skill)
    return skill


async def delete_skill(db: AsyncSession, user_id: str, skill_id: str) -> Skill | None:
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.owner_id == user_id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        return None

    await db.delete(skill)
    await db.commit()
    return skill
