from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.workflow import WorkflowChatRequest, WorkflowCreate, WorkflowResponse, WorkflowUpdate
from app.services import workflow_service
from app.services.workflow_runner import run_workflow_stream

router = APIRouter()


@router.get("/workflows", response_model=list[WorkflowResponse])
async def list_workflows(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await workflow_service.get_workflows(db, user.id)


@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(data: WorkflowCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await workflow_service.create_workflow(db, user.id, data)


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def read_workflow(workflow_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    workflow = await workflow_service.get_workflow(db, user.id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflowが見つかりません。")
    return workflow


@router.patch("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    data: WorkflowUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workflow = await workflow_service.update_workflow(db, user.id, workflow_id, data)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflowが見つかりません。")
    return workflow


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    deleted = await workflow_service.delete_workflow(db, user.id, workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflowが見つかりません。")
    return {"status": "deleted"}


def _sse(payload: dict) -> str:
    import json
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/workflows/{workflow_id}/chat")
async def chat_with_workflow(
    workflow_id: str,
    payload: WorkflowChatRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workflow = await workflow_service.get_workflow(db, user.id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflowが見つかりません。")

    async def stream():
        async for event in run_workflow_stream(db, workflow, str(user.id), payload.message):
            yield _sse(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
