"""job_manager / jobs API (再開可能SSE) のテスト。"""
import asyncio
import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.api import auth as auth_module


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def client(test_engine):
    factory = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db():
        async with factory() as session:
            yield session

    application = FastAPI()
    application.include_router(auth_router, prefix="/api")
    application.include_router(jobs_router, prefix="/api", tags=["jobs"])
    from app.core.database import get_db as original_get_db
    from app.api.deps import get_db as deps_get_db

    application.dependency_overrides = {}
    application.dependency_overrides[original_get_db] = _get_db
    application.dependency_overrides[deps_get_db] = _get_db
    application.dependency_overrides[auth_module.get_db] = _get_db

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture()
async def auth_headers(client: AsyncClient):
    await client.post("/api/auth/register", data={"username": "jobuser", "email": "job@example.com", "password": "secret"})
    login = (await client.post("/api/auth/login", data={"username": "jobuser", "password": "secret"})).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


# ---- job_manager 単体 ----


@pytest.mark.asyncio
async def test_stream_events_replays_history_after_disconnect():
    from app.services import job_manager

    job_id = job_manager.create_job("agent", "ref-1", "hello", "user-1")
    # 3イベント発行して完了
    for i in range(3):
        job_manager.publish_event(job_id, {"type": "delta", "content": f"chunk{i}"})
    job_manager.finish_job(job_id, "completed")

    # since=0 → 全イベント再生
    events = []
    async for seq, ev in job_manager.stream_events(job_id, 0):
        events.append((seq, ev))
    assert len(events) == 3
    assert [seq for seq, _ in events] == [1, 2, 3]

    # Last-Event-ID 相当: seq=1 以降のみ再生
    events2 = []
    async for seq, ev in job_manager.stream_events(job_id, 1):
        events2.append((seq, ev))
    assert [seq for seq, _ in events2] == [2, 3]


@pytest.mark.asyncio
async def test_stream_events_live_delivery():
    from app.services import job_manager

    job_id = job_manager.create_job("agent", "ref-1", "hello", "user-1")

    async def consume():
        events = []
        async for seq, ev in job_manager.stream_events(job_id, 0):
            events.append((seq, ev))
            if len(events) >= 2:
                break
        return events

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    job_manager.publish_event(job_id, {"type": "delta", "content": "live1"})
    await asyncio.sleep(0.05)
    job_manager.publish_event(job_id, {"type": "delta", "content": "live2"})

    events = await asyncio.wait_for(consumer, timeout=5)
    assert [ev["content"] for _, ev in events] == ["live1", "live2"]

    job_manager.finish_job(job_id, "completed")


# ---- API 結合 (runner をモック) ----


@pytest.mark.asyncio
async def test_create_job_and_resume_sse(client: AsyncClient, auth_headers, monkeypatch):
    from app.api import jobs as jobs_api

    # 実行本体を差し替え: 3イベント発行後に完了
    async def fake_execute(job_id, db_factory):
        from app.services import job_manager
        for i in range(3):
            job_manager.publish_event(job_id, {"type": "delta", "content": f"c{i}"})
        job_manager.finish_job(job_id, "completed")

    monkeypatch.setattr(jobs_api, "_execute_job", fake_execute)

    created = await client.post(
        "/api/jobs",
        json={"kind": "agent", "ref_id": "agent-x", "message": "hi"},
        headers=auth_headers,
    )
    assert created.status_code == 202, created.text
    job_id = created.json()["id"]

    # タスク完了を待つ
    for _ in range(50):
        jobs_list = (await client.get("/api/jobs", headers=auth_headers)).json()
        if any(j["id"] == job_id and j["status"] != "running" for j in jobs_list):
            break
        await asyncio.sleep(0.1)

    # SSE: since=0 で全履歴取得
    resp = await client.get(f"/api/jobs/{job_id}/events?since=0", headers=auth_headers)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    lines = [l for l in resp.text.split("\n") if l.startswith("id:")]
    ids = [int(l.split(":", 1)[1]) for l in lines]
    assert ids == [1, 2, 3]

    # 再開: Last-Event-ID=1 → id 2,3 のみ
    resp2 = await client.get(
        f"/api/jobs/{job_id}/events",
        headers={**auth_headers, "Last-Event-ID": "1"},
    )
    ids2 = [int(l.split(":", 1)[1]) for l in resp2.text.split("\n") if l.startswith("id:")]
    assert ids2 == [2, 3]
