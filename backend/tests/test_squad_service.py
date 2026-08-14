import pytest

from app.models.agent import Agent as AgentModel
from app.models.user import User
from app.schemas.squad import SquadCreate
from app.services.squad_service import create_squad, get_squads, get_squad


@pytest.mark.asyncio
async def test_create_squad_only_selected_agents(db_session):
    user = User(id="user-1", username="tester", email="tester@example.com", hashed_password="hashed")
    agent_one = AgentModel(
        id="agent-1",
        title="Agent One",
        description="Agent One desc",
        system_prompt="Prompt 1",
        model_provider="openai",
        model_id="gpt-4o",
        visibility="private",
        ad_group=None,
        mcp_server_id=None,
        skill_ids=[],
        owner_id=user.id,
    )
    agent_two = AgentModel(
        id="agent-2",
        title="Agent Two",
        description="Agent Two desc",
        system_prompt="Prompt 2",
        model_provider="openai",
        model_id="gpt-4o-mini",
        visibility="private",
        ad_group=None,
        mcp_server_id=None,
        skill_ids=[],
        owner_id=user.id,
    )
    db_session.add_all([user, agent_one, agent_two])
    await db_session.commit()

    squad = await create_squad(
        db_session,
        user.id,
        SquadCreate(
            name="My Squad",
            description="Test squad",
            system_prompt="Team up",
            model_provider="openai",
            model_id="gpt-4o-mini",
            leader_agent_id=agent_one.id,
            team_agent_ids=[agent_two.id],
            visibility="private",
        ),
    )

    assert [member.agent_id for member in squad.members if member.role == "leader"] == [agent_one.id]
    assert [member.agent_id for member in squad.members if member.role == "member"] == [agent_two.id]

    loaded = await get_squad(db_session, user.id, squad.id)
    assert loaded is not None
    assert [member.agent_id for member in loaded.members if member.role == "leader"] == [agent_one.id]

    squads = await get_squads(db_session, user.id)
    assert len(squads) == 1
    assert [member.agent_id for member in squads[0].members if member.role == "leader"] == [agent_one.id]
