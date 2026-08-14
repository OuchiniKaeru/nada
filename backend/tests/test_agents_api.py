import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.core.database import Base
from app.core.security import create_access_token
from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.agents import router as agents_router
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
        data={"username": "dave", "email": "dave@example.com", "password": "secret"},
    )
    login = (
        await client.post(
            "/api/auth/login",
            data={"username": "dave", "password": "secret"},
        )
    ).json()
    return login["access_token"]


@pytest.mark.asyncio
async def test_create_agent_returns_created_agent(client: AsyncClient, authenticated_user: str):
    response = await client.post(
        "/api/agents",
        json={
            "title": "Test Agent",
            "description": "A test agent",
            "system_prompt": "You are helpful.",
            "model_provider": "openai",
            "model_id": "gpt-4o-mini",
            "visibility": "private",
        },
        headers={"Authorization": f"Bearer {authenticated_user}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["title"] == "Test Agent"
    assert data["visibility"] == "private"
    assert "id" in data


@pytest.mark.asyncio
async def test_unauthenticated_create_agent_returns_401(client: AsyncClient):
    response = await client.post(
        "/api/agents",
        json={
            "title": "No Auth Agent",
            "description": "Should fail",
            "system_prompt": "You are helpful.",
            "model_provider": "openai",
            "model_id": "gpt-4o-mini",
        },
    )
    assert response.status_code == 401
