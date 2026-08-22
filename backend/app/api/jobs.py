from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal
import asyncio

from app.api.deps import get_current_user, get_db
from app.services import job_manager

router = APIRouter()


class JobCreate(BaseModel):
    kind: Literal["agent", "squad", "workflow"]
    ref_id: str
    message: str


class JobResponse(BaseModel):
    id: str
    kind: str
    ref_id: str
    status: str


def _sse(seq: int, payload: dict) -> str:
    import json
    return f"id: {seq}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _execute_job(job_id: str, db_factory):
    """ジョブ本体を実行し、イベントを job_manager に発行する。"""
    from sqlalchemy import select
    from app.models.agent import Agent as AgentModel
    from app.models.squad import Squad
    from app.services.workflow_runner import run_workflow_stream
    from app.runtime.agent_runtime import AgentRuntime, SquadChatRuntime

    job = job_manager.get_job(job_id)
    kind = job["kind"]
    ref_id = job["ref_id"]
    message = job["message"]

    async with db_factory() as db:
        try:
            if kind == "workflow":
                from app.services.workflow_service import get_workflow
                wf = await get_workflow(db, job["user_id"], ref_id)
                if not wf:
                    raise ValueError("Workflowが見つかりません。")
                final = []
                async for event in run_workflow_stream(db, wf, job["user_id"], message):
                    job_manager.publish_event(job_id, event)
                    if event["type"] == "workflow_done":
                        final = event.get("outputs", [])
                        raise StopIteration
            else:
                if kind == "squad":
                    result = await db.execute(select(Squad).where(Squad.id == ref_id))
                    squad = result.scalar_one_or_none()
                    if not squad:
                        raise ValueError("スクワッドが見つかりません。")
                    runtime = SquadChatRuntime(squad, db)
                else:
                    runtime = AgentRuntime(ref_id, db, user_id=job["user_id"])
                parts = []
                async for chunk in runtime.astream(message):
                    parts.append(chunk)
                    job_manager.publish_event(job_id, {"type": "delta", "content": chunk})
                final = ["".join(parts)]

            job_manager.finish_job(job_id, "completed", (final[-1] if final else "")[:200])
        except StopIteration:
            pass
        except asyncio.CancelledError:
            job_manager.finish_job(job_id, "cancelled")
        except Exception as exc:
            job_manager.publish_event(job_id, {"type": "error", "message": str(exc)})
            job_manager.finish_job(job_id, "failed", str(exc)[:200])


@router.post("/jobs", response_model=JobResponse, status_code=202)
async def create_job(data: JobCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.core.database import AsyncSessionLocal

    job_id = job_manager.create_job(data.kind, data.ref_id, data.message, str(user.id))
    job_manager.get_job(job_id)["task"] = asyncio.get_running_loop().create_task(
        _execute_job(job_id, AsyncSessionLocal)
    )
    return JobResponse(id=job_id, kind=data.kind, ref_id=data.ref_id, status="running")


@router.get("/jobs")
async def list_jobs(user=Depends(get_current_user)):
    return job_manager.list_jobs(str(user.id))


@router.get("/jobs/{job_id}/events")
async def stream_job_events(
    job_id: str,
    request: Request,
    since: int = Query(default=0, ge=0, description="このseq以降のイベントを再生"),
    user=Depends(get_current_user),
):
    # EventSource 標準の Last-Event-ID ヘッダを優先
    last_event_id = request.headers.get("last-event-id")
    if last_event_id:
        try:
            since = max(since, int(last_event_id))
        except ValueError:
            pass

    try:
        job_manager.get_job(job_id)
    except job_manager.JobNotFound:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。")

    async def stream():
        async for seq, ev in job_manager.stream_events(job_id, since):
            yield _sse(seq, ev)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str, user=Depends(get_current_user)):
    try:
        cancelled = await job_manager.cancel_job(job_id)
    except job_manager.JobNotFound:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。")
    return {"status": "cancelled" if cancelled else "not_running"}
