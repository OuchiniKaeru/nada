from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.models.skill import Skill
from app.schemas.skill import SkillCreate, SkillResponse, SkillUpdate
from app.services.skill_service import create_skill, get_skills, update_skill, delete_skill

router = APIRouter()


@router.get("/skills", response_model=list[SkillResponse])
async def list_skills(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_skills(db, user.id)


@router.get("/skills/{skill_id}", response_model=SkillResponse)
async def read_skill(skill_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Skill).where(Skill.id == skill_id, Skill.owner_id == user.id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skillが見つかりません。")
    return skill


@router.post("/skills", response_model=SkillResponse)
async def create_skill_endpoint(data: SkillCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await create_skill(db, user.id, data)


@router.patch("/skills/{skill_id}", response_model=SkillResponse)
async def update_skill_endpoint(skill_id: str, data: SkillUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    skill = await update_skill(db, user.id, skill_id, data)
    if not skill:
        raise HTTPException(status_code=404, detail="Skillが見つかりません。")
    return skill


@router.delete("/skills/{skill_id}")
async def delete_skill_endpoint(skill_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    skill = await delete_skill(db, user.id, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skillが見つかりません。")
    return {"id": skill.id}
