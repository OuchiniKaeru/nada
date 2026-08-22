import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.core.database import Base
from app.core.security import create_access_token
from fastapi import FastAPI
from app.api.auth import router as auth_router
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

    application = FastAPI()
    application.include_router(auth_router, prefix="/api")
    application.dependency_overrides = {}

    async def override_get_db():
        yield db_session

    from app.core.database import get_db as original_get_db
    from app.api import auth as auth_module

    application.dependency_overrides[original_get_db] = override_get_db
    application.dependency_overrides[auth_module.get_db] = override_get_db

    return application


@pytest_asyncio.fixture()
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        data={"username": "alice", "email": "alice@example.com", "password": "secret"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "alice"
    assert "id" in data


@pytest.mark.asyncio
async def test_login_returns_token(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        data={"username": "bob", "email": "bob@example.com", "password": "secret"},
    )

    response = await client.post(
        "/api/auth/login",
        data={"username": "bob", "password": "secret"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data


@pytest.mark.asyncio
async def test_get_me_with_valid_token(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        data={"username": "carol", "email": "carol@example.com", "password": "secret"},
    )

    login = (
        await client.post(
            "/api/auth/login",
            data={"username": "carol", "password": "secret"},
        )
    ).json()
    token = login["access_token"]

    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "carol"


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client: AsyncClient):
    response = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401
