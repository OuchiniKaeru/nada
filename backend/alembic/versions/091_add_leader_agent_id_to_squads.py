"""add_leader_agent_id_to_squads"""

from alembic import op
import sqlalchemy as sa


revision = "091_add_leader_agent"
down_revision = "090_add_agent_mcp_server_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = {col["name"] for col in insp.get_columns("squads")}
    if "leader_agent_id" not in columns:
        op.add_column(
            "squads",
            sa.Column("leader_agent_id", sa.String(length=36), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = {col["name"] for col in insp.get_columns("squads")}
    if "leader_agent_id" in columns:
        op.drop_column("squads", "leader_agent_id")
