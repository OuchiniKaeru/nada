from agno.agent import Agent

import pytest

from app.services.agent_factory import AgentFactory


class DummyAgent:
    def __init__(self, *, title=None, system_prompt="", model_provider=None, model_id=None):
        self.title = title
        self.system_prompt = system_prompt
        self.model_provider = model_provider
        self.model_id = model_id

    async def arun(self, message, session_id=None, user_id=None):
        class _Run:
            content = message
        return _Run()


@pytest.mark.asyncio
async def test_create_agent_returns_agno_agent(monkeypatch):
    captured = {}

    class FakeAgent(Agent):
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "app.services.agent_factory.Agent",
        FakeAgent,
        raising=False,
    )

    cfg = DummyAgent(
        title="Test Agent",
        system_prompt="You are helpful.",
        model_provider="openai",
        model_id="gpt-4o",
    )
    agent = await AgentFactory.create_agent(cfg)

    assert isinstance(agent, Agent)
    assert captured["name"] == "Test Agent"
    assert captured["instructions"] == "You are helpful."
    assert captured["tools"] == []


def test_load_model_unsupported_provider_raises():
    from app.services.agent_factory import _load_model

    with pytest.raises(ValueError, match="Unsupported model provider"):
        _load_model("unknown", "x")


@pytest.mark.asyncio
async def test_runtime_run_returns_response_without_raising(monkeypatch):
    from app.runtime.agent_runtime import AgentRuntime

    async def fake_load_agent_definition(self):
        class _Cfg:
            title = "Agent One"
            system_prompt = "You are a test agent."
            model_provider = "openai"
            model_id = "gpt-4o"
            skill_ids = []
            mcp_server_id = None
            skills = []
            mcp = None

        return _Cfg()

    class FakeAgentFactory:
        @staticmethod
        async def create_agent(config, *, session_id=None, user_id=None):
            return DummyAgent(title=str(getattr(config, "title", "")))

    monkeypatch.setattr(
        AgentRuntime,
        "_load_agent_definition",
        fake_load_agent_definition,
        raising=False,
    )
    monkeypatch.setattr(
        "app.runtime.agent_runtime.AgentFactory",
        FakeAgentFactory,
        raising=False,
    )

    async def _noop():
        return None

    monkeypatch.setattr(
        "app.runtime.agent_runtime.close_agno_postgres_db",
        _noop,
        raising=False,
    )

    runtime = AgentRuntime("agent-1", None)
    response = await runtime.run("hello", [])

    assert isinstance(response, str)
    assert response == "hello"


@pytest.mark.asyncio
async def test_runtime_loads_selected_skills_and_mcp(db_session, monkeypatch):
    from app.models.agent import Agent as AgentModel
    from app.models.skill import Skill
    from app.models.mcp import MCPServer
    from app.models.user import User
    from app.runtime.agent_runtime import AgentRuntime

    user = User(id="user-2", username="tester2", email="tester2@example.com", hashed_password="hashed")
    skill = Skill(
        id="skill-1",
        name="Example Skill",
        description="A skill",
        content="Use this skill for testing.",
        visibility="private",
        owner_id=user.id,
    )
    mcp = MCPServer(
        id="mcp-1",
        name="Example MCP",
        description="Test MCP",
        url="https://mcp.example.com",
        transport="sse",
        auth_type="none",
        auth_secret_encrypted=None,
        enabled=True,
        owner_id=user.id,
    )
    agent = AgentModel(
        id="agent-rt-2",
        title="Agent Two",
        description="Agent Two desc",
        system_prompt="Prompt two",
        model_provider="openai",
        model_id="gpt-4o",
        visibility="private",
        ad_group=None,
        mcp_server_id=mcp.id,
        skill_ids=[skill.id],
        owner_id=user.id,
    )
    db_session.add_all([user, skill, mcp, agent])
    await db_session.commit()

    created = {}

    class FakeAgentFactory:
        @staticmethod
        async def create_agent(config, *, session_id=None, user_id=None):
            created["config"] = config
            return DummyAgent(title="Agent Two")

    async def _noop():
        return None

    monkeypatch.setattr(
        "app.runtime.agent_runtime.AgentFactory",
        FakeAgentFactory,
        raising=False,
    )
    monkeypatch.setattr(
        "app.runtime.agent_runtime.close_agno_postgres_db",
        _noop,
        raising=False,
    )

    runtime = AgentRuntime(agent.id, db_session)
    response = await runtime.run("hello", [])

    assert isinstance(response, str)
    assert response == "hello"
    assert created["config"].title == "Agent Two"
    assert created["config"].skills == [skill]
    assert created["config"].mcp == [mcp]
