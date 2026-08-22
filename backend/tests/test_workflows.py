"""Workflow API / runner のテスト。"""
import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.workflows import router as workflows_router
from app.api import auth as auth_module


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(test_engine):
    factory = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await session.begin()
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def client(db_session):
    async def _get_db():
        yield db_session

    application = FastAPI()
    application.include_router(auth_router, prefix="/api")
    application.include_router(workflows_router, prefix="/api", tags=["workflows"])
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
    await client.post("/api/auth/register", data={"username": "wfuser", "email": "wf@example.com", "password": "secret"})
    login = (await client.post("/api/auth/login", data={"username": "wfuser", "password": "secret"})).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


@pytest.mark.asyncio
async def test_workflow_crud(client: AsyncClient, auth_headers):
    created = (await client.post(
        "/api/workflows",
        json={
            "name": "WF1",
            "description": "test workflow",
            "visibility": "private",
            "steps": [
                {"kind": "agent", "ref_id": "agent-1", "prompt_template": ""},
                {"kind": "squad", "ref_id": "squad-1", "prompt_template": ""},
            ],
        },
        headers=auth_headers,
    )).json()
    assert created["name"] == "WF1"
    assert len(created["steps"]) == 2

    listed = (await client.get("/api/workflows", headers=auth_headers)).json()
    assert any(w["id"] == created["id"] for w in listed)

    upd = await client.patch(
        f"/api/workflows/{created['id']}",
        json={"description": "updated"},
        headers=auth_headers,
    )
    assert upd.json()["description"] == "updated"

    dele = await client.delete(f"/api/workflows/{created['id']}", headers=auth_headers)
    assert dele.status_code == 200


def _parse_sse_events(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line.split(":", 1)[1]))
    return events


@pytest.mark.asyncio
async def test_workflow_chat_streams_step_events(client: AsyncClient, auth_headers, db_session, monkeypatch):
    # Workflow作成 (存在しないagent参照でも、runnerをモックすれば通る)
    wf = (await client.post(
        "/api/workflows",
        json={
            "name": "WF-chat",
            "description": "",
            "visibility": "private",
            "steps": [
                {"kind": "agent", "ref_id": "fake-agent-1"},
                {"kind": "agent", "ref_id": "fake-agent-2"},
            ],
        },
        headers=auth_headers,
    )).json()

    # runner の _run_step をモックして LLM 呼び出しを回避
    from app.services import workflow_runner

    async def fake_run_step(db, user_id, step, message):
        return f"out({step['ref_id']})"

    monkeypatch.setattr(workflow_runner, "_run_step", fake_run_step)

    resp = await client.post(
        f"/api/workflows/{wf['id']}/chat",
        json={"message": "開始"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(resp.text)
    types = [e["type"] for e in events]
    assert types.count("step_started") == 2
    assert types.count("step_completed") == 2
    assert types[-1] == "workflow_done"

    done = events[-1]
    assert done["outputs"] == ["out(fake-agent-1)", "out(fake-agent-2)"]
