import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
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
    resource,
    workflow,
)

EXPECTED_TABLES = {
    "users",
    "agents",
    "agent_permissions",
    "skills",
    "mcp_servers",
    "squads",
    "squad_members",
    "sessions",
    "messages",
    "attachments",
    "executions",
    "execution_agents",
    "model_registry",
    "model_prices",
    # Phase 2: リソース基盤
    "resources",
    "resource_links",
    # Phase 3: Workflow
    "workflows",
}


@pytest.fixture(scope="session")
def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine.sync_engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(test_engine):
    return sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_metadata_contains_expected_tables():
    assert Base.metadata.tables.keys() >= EXPECTED_TABLES


@pytest.mark.asyncio
async def test_table_names_match_spec():
    assert Base.metadata.tables.keys() == EXPECTED_TABLES


@pytest.mark.asyncio
async def test_user_columns_exist():
    columns = {c.name for c in Base.metadata.tables["users"].columns}
    expected = {"id", "username", "email", "hashed_password", "is_active", "is_admin", "created_at"}
    assert expected.issubset(columns)


@pytest.mark.asyncio
async def test_agent_columns_exist():
    columns = {c.name for c in Base.metadata.tables["agents"].columns}
    expected = {"id", "title", "description", "system_prompt", "model_provider", "model_id", "owner_id", "visibility", "status", "created_at", "updated_at"}
    assert expected.issubset(columns)


@pytest.mark.asyncio
async def test_execution_columns_exist():
    columns = {c.name for c in Base.metadata.tables["executions"].columns}
    expected = {"id", "user_id", "agent_id", "session_id", "squad_id", "model", "input_tokens", "output_tokens", "total_tokens", "cost", "duration_ms", "status", "created_at"}
    assert expected.issubset(columns)


@pytest.mark.asyncio
async def test_model_price_columns_exist():
    columns = {c.name for c in Base.metadata.tables["model_prices"].columns}
    expected = {"id", "provider", "model_id", "input_price", "output_price", "currency", "effective_from", "created_at"}
    assert expected.issubset(columns)
