"""add skill_ids and mcp_server_id to agents

Revision ID: 089_add_agent_skill_ids
Revises: 0880307a34ca
Create Date: 2026-08-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "089_add_agent_skill_ids"
down_revision = "0880307a34ca"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("mcp_server_id", sa.String(length=36), nullable=True),
        )
        batch_op.add_column(
            sa.Column("skill_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        )
        batch_op.create_foreign_key(
            "fk_agents_mcp_server_id",
            "mcp_servers",
            ["mcp_server_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_constraint("fk_agents_mcp_server_id")
        batch_op.drop_column("skill_ids")
        batch_op.drop_column("mcp_server_id")
