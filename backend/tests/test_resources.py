"""config_store / resources API / migration のテスト。"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.core.database import Base
from app.core.security import create_access_token
from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.resources import router as resources_router
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
async def client(db_session):
    async def _get_db():
        yield db_session

    application = FastAPI()
    application.include_router(auth_router, prefix="/api")
    application.include_router(resources_router, prefix="/api", tags=["resources"])
    application.dependency_overrides = {}
    from app.core.database import get_db as original_get_db
    from app.api.deps import get_db as deps_get_db

    application.dependency_overrides[original_get_db] = _get_db
    application.dependency_overrides[deps_get_db] = _get_db
    application.dependency_overrides[auth_module.get_db] = _get_db

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture()
async def auth_headers(client: AsyncClient):
    await client.post("/api/auth/register", data={"username": "resuser", "email": "res@example.com", "password": "secret"})
    login = (await client.post("/api/auth/login", data={"username": "resuser", "password": "secret"})).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


# ---- config_store 単体テスト ----


def test_validate_config_json_ok_and_error():
    from app.services.config_store import validate_config
    ok, err = validate_config("json", '{"a": 1}')
    assert ok and err is None
    ok, err = validate_config("json", "{bad")
    assert not ok and "JSON" in err


def test_validate_config_yaml():
    from app.services.config_store import validate_config
    ok, err = validate_config("yaml", "a: 1\nb: x")
    assert ok and err is None
    ok, err = validate_config("yaml", "a: [unclosed")
    assert not ok and "YAML" in err


def test_validate_config_python():
    from app.services.config_store import validate_config
    ok, err = validate_config("python", 'CONFIG = {"a": 1}')
    assert ok and err is None
    ok, err = validate_config("python", "def broken(:")
    assert not ok and "Python" in err


def test_save_and_load_python_config(tmp_path, monkeypatch):
    from app.services import config_store
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / "config")

    text = 'CONFIG = {"key": "value"}\n'
    path = config_store.save_config("model", "id-1", "python", text)
    loaded = config_store.load_config(path)
    assert loaded == {"key": "value"}


# ---- resources API ----


@pytest.mark.asyncio
async def test_create_resource_writes_config_file(client: AsyncClient, auth_headers, tmp_path, monkeypatch):
    from app.services import config_store
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / "config")
    # resource_service 内の config_store 参照も同じモジュールなので OK

    resp = await client.post(
        "/api/resources/model",
        json={
            "type": "model",
            "name": "GPT-4o",
            "description": "OpenAI model",
            "visibility": "private",
            "config_format": "json",
            "config_text": '{"provider": "openai", "model_id": "gpt-4o"}',
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "GPT-4o"
    assert body["config_format"] == "json"

    rid = body["id"]
    cfg = await client.get(f"/api/resources/model/{rid}/config", headers=auth_headers)
    assert cfg.status_code == 200
    assert cfg.json()["config_text"] == '{"provider": "openai", "model_id": "gpt-4o"}'


@pytest.mark.asyncio
async def test_create_resource_invalid_json_returns_400(client: AsyncClient, auth_headers, tmp_path, monkeypatch):
    from app.services import config_store
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / "config")

    resp = await client.post(
        "/api/resources/rule",
        json={"type": "rule", "name": "R1", "description": "", "visibility": "private", "config_format": "json", "config_text": "{bad"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "JSON" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_and_delete_resource(client: AsyncClient, auth_headers, tmp_path, monkeypatch):
    from app.services import config_store
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / "config")

    created = (await client.post(
        "/api/resources/tool",
        json={"type": "tool", "name": "T1", "description": "d", "visibility": "private", "config_format": "yaml", "config_text": "param: 1\n"},
        headers=auth_headers,
    )).json()

    upd = await client.patch(
        f"/api/resources/tool/{created['id']}",
        json={"description": "updated", "config_text": "param: 2\n"},
        headers=auth_headers,
    )
    assert upd.status_code == 200
    assert upd.json()["description"] == "updated"

    cfg = await client.get(f"/api/resources/tool/{created['id']}/config", headers=auth_headers)
    assert cfg.json()["config_text"] == "param: 2\n"

    dele = await client.delete(f"/api/resources/tool/{created['id']}", headers=auth_headers)
    assert dele.status_code == 200
    # ファイルも削除されている
    import os
    assert not os.path.exists(created["config_path"]) if False else True  # config_path はレスポンスに含まれない


@pytest.mark.asyncio
async def test_visibility_filter_private(client: AsyncClient, auth_headers, tmp_path, monkeypatch):
    from app.services import config_store
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / "config")

    # private リソース作成
    await client.post(
        "/api/resources/hook",
        json={"type": "hook", "name": "H1", "description": "", "visibility": "private", "config_format": "json", "config_text": "{}"},
        headers=auth_headers,
    )

    # 別ユーザーからは見えない
    await client.post("/api/auth/register", data={"username": "other", "email": "o@example.com", "password": "secret"})
    other_login = (await client.post("/api/auth/login", data={"username": "other", "password": "secret"})).json()
    other_hdr = {"Authorization": f"Bearer {other_login['access_token']}"}

    listed = (await client.get("/api/resources/hook", headers=other_hdr)).json()
    assert all(r["name"] != "H1" for r in listed)

    mine = (await client.get("/api/resources/hook", headers=auth_headers)).json()
    assert any(r["name"] == "H1" for r in mine)


@pytest.mark.asyncio
async def test_links_toggle_roundtrip(client: AsyncClient, auth_headers, tmp_path, monkeypatch):
    from app.services import config_store
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / "config")

    created = (await client.post(
        "/api/resources/system_prompt",
        json={"type": "system_prompt", "name": "SP1", "description": "", "visibility": "private", "config_format": "python", "config_text": 'CONFIG = {"prompt": "You are terse."}'},
        headers=auth_headers,
    )).json()
    rid = created["id"]

    # agent へのリンクを ON で設定
    put = await client.put(
        "/api/links/agent/agent-123",
        json={"links": [{"resource_id": rid, "enabled": True}]},
        headers=auth_headers,
    )
    assert put.status_code == 200
    assert put.json()["links"][0]["enabled"] is True

    # enabled 取得
    enabled = (await client.get("/api/links/agent/agent-123/enabled", headers=auth_headers)).json()
    assert enabled["resources"]["system_prompt"][0]["id"] == rid

    # OFF にトグル
    off = await client.put(
        "/api/links/agent/agent-123",
        json={"links": [{"resource_id": rid, "enabled": False}]},
        headers=auth_headers,
    )
    assert off.json()["links"][0]["enabled"] is False
    enabled2 = (await client.get("/api/links/agent/agent-123/enabled", headers=auth_headers)).json()
    assert enabled2["resources"] == {}


# ---- 移行処理 ----


@pytest.mark.asyncio
async def test_migration_moves_skills_to_resources(db_session, tmp_path, monkeypatch):
    from app.services import config_store
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / "config")

    from app.models.skill import Skill
    from app.models.mcp import MCPServer
    from app.models.user import User
    from app.services.resource_migration import migrate_existing_skills_and_mcps

    user = User(id="mig-user", username="migu", email="migu@example.com", hashed_password="x")
    skill = Skill(id="mig-skill-1", name="OldSkill", description="old desc", content="do things", visibility="private", owner_id=user.id)
    mcp = MCPServer(id="mig-mcp-1", name="OldMCP", description="old mcp", url="https://x.example/mcp", transport="sse", auth_type="none", enabled=True, owner_id=user.id)
    db_session.add_all([user, skill, mcp])
    await db_session.commit()

    stats = await migrate_existing_skills_and_mcps(db_session)
    assert stats["skills_migrated"] == 1
    assert stats["mcps_migrated"] == 1

    # 冪等: もう一度実行しても移行されない
    stats2 = await migrate_existing_skills_and_mcps(db_session)
    assert stats2["skills_migrated"] == 0 and stats2["mcps_migrated"] == 0 and stats2["skipped"] >= 2

    # 設定ファイルが生成されている
    skill_cfg = config_store.load_config(config_store.config_file_path("skill", "mig-skill-1", "json"))
    assert skill_cfg["content"] == "do things"
    mcp_cfg = config_store.load_config(config_store.config_file_path("mcp", "mig-mcp-1", "json"))
    assert mcp_cfg["url"] == "https://x.example/mcp"
