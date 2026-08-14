import pytest_asyncio
from httpx import AsyncClient

from app.core.database import Base, get_db as original_get_db
from app.core.security import create_access_token
from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api import auth as auth_module
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Ensure all model tables are registered with SQLAlchemy metadata for tests
from app.models import (
    user,
    agent,
    agent_permission,
    skill,
    mcp,
    squad,
    squad_member,
    session as session_model,
    message,
    attachment,
    execution,
    execution_agent,
    model_registry,
    model_price,
)


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
        nested = await session.begin_nested()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def restart_savepoint(sess, transaction):
            if transaction.nested and not transaction._parent.nested:
                sess.begin_nested()

        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def app(db_session):
    async def _get_db():
        yield db_session

    application = FastAPI()
    application.include_router(auth_router)

    application.dependency_overrides = {}
    application.dependency_overrides[original_get_db] = _get_db
    application.dependency_overrides[auth_module.get_db] = _get_db

    return application


@pytest_asyncio.fixture()
async def client(app: FastAPI):
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture()
def make_token():
    def _make(user_id: str, username: str):
        return create_access_token(data={"sub": user_id, "username": username})
    return _make
