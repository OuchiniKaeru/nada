import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate


def _visibility_filter(workflow: Workflow, user_id: str):
    return (workflow.visibility != "private") | (workflow.owner_id == user_id)


async def create_workflow(db: AsyncSession, user_id: str, data: WorkflowCreate) -> Workflow:
    workflow = Workflow(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        visibility=data.visibility,
        steps=[step.model_dump() for step in data.steps],
        owner_id=user_id,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def get_workflows(db: AsyncSession, user_id: str) -> list[Workflow]:
    result = await db.execute(
        select(Workflow).where(_visibility_filter(Workflow, user_id)).order_by(Workflow.created_at.desc())
    )
    return list(result.scalars().all())


async def get_workflow(db: AsyncSession, user_id: str, workflow_id: str) -> Workflow | None:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow or not _visibility_filter(workflow, user_id):
        return None
    return workflow


async def update_workflow(db: AsyncSession, user_id: str, workflow_id: str, data: WorkflowUpdate) -> Workflow | None:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data:
        workflow.name = update_data["name"]
    if "description" in update_data:
        workflow.description = update_data["description"]
    if "visibility" in update_data:
        workflow.visibility = update_data["visibility"]
    if "steps" in update_data:
        workflow.steps = [s if isinstance(s, dict) else s for s in update_data["steps"]]

    await db.commit()
    await db.refresh(workflow)
    return workflow


async def delete_workflow(db: AsyncSession, user_id: str, workflow_id: str) -> bool:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == user_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        return False
    await db.delete(workflow)
    await db.commit()
    return True
