import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.core.database import Base
from app.core.security import create_access_token
from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.agents import router as agents_router
from app.api.chat import router as chat_router
from app.api import auth as auth_module
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


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
async def app(db_session):
    async def _get_db():
        yield db_session

    from app.core.database import get_db as original_get_db
    from app.api.deps import get_db as deps_get_db

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(agents_router, prefix="/api", tags=["agents"])
    application.include_router(chat_router, prefix="/api", tags=["chat"])

    application.dependency_overrides = {}
    application.dependency_overrides[original_get_db] = _get_db
    application.dependency_overrides[deps_get_db] = _get_db
    application.dependency_overrides[auth_module.get_db] = _get_db

    return application


@pytest_asyncio.fixture()
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture()
async def authenticated_user(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        data={"username": "eve", "email": "eve@example.com", "password": "secret"},
    )
    login = (
        await client.post(
            "/api/auth/login",
            data={"username": "eve", "password": "secret"},
        )
    ).json()
    return login["access_token"]


@pytest_asyncio.fixture()
async def agent_id(client: AsyncClient, authenticated_user: str):
    response = await client.post(
        "/api/agents",
        json={
            "title": "Chat Agent",
            "description": "A chat agent",
            "system_prompt": "You are helpful.",
            "model_provider": "openai",
            "model_id": "gpt-4o-mini",
            "visibility": "private",
        },
        headers={"Authorization": f"Bearer {authenticated_user}"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _parse_sse_text(text: str) -> dict:
    event = {}
    event_name = None
    data_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip("\r")
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
    if event_name is None:
        raise AssertionError(f"No SSE event name found in: {text!r}")
    event["event"] = event_name
    event["data"] = "".join(data_lines)
    return event


@pytest.mark.asyncio
async def test_chat_returns_sse_stream(client: AsyncClient, authenticated_user: str, agent_id: str):
    response = await client.post(
        f"/api/agents/{agent_id}/chat",
        json={"message": "Hello from SSE test"},
        headers={"Authorization": f"Bearer {authenticated_user}"},
    )
    assert response.status_code == 200, response.text
    body = response.text
    parsed = _parse_sse_text(body)
    assert parsed["event"] == "message"
    payload = json.loads(parsed["data"])
    assert payload["content"] == "placeholder response to: Hello from SSE test"
    assert "session_id" in payload and payload["session_id"]
    assert "message_id" in payload and payload["message_id"]


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient, authenticated_user: str, agent_id: str):
    await client.post(
        f"/api/agents/{agent_id}/chat",
        json={"message": "First message"},
        headers={"Authorization": f"Bearer {authenticated_user}"},
    )

    response = await client.get(
        f"/api/agents/{agent_id}/sessions",
        headers={"Authorization": f"Bearer {authenticated_user}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["agent_id"] == agent_id


@pytest.mark.asyncio
async def test_unauthenticated_chat_returns_401(client: AsyncClient, agent_id: str):
    response = await client.post(
        f"/api/agents/{agent_id}/chat",
        json={"message": "No auth"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_list_sessions_returns_401(client: AsyncClient, agent_id: str):
    response = await client.get(
        f"/api/agents/{agent_id}/sessions",
    )
    assert response.status_code == 401
