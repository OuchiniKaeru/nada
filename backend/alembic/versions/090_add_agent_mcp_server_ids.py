"""add mcp_server_ids to agents

Revision ID: 090_add_agent_mcp_server_ids
Revises: 089_add_agent_skill_ids
Create Date: 2026-08-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "090_add_agent_mcp_server_ids"
down_revision = "089_add_agent_skill_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("mcp_server_ids", sa.JSON(), nullable=True, server_default=sa.text("'[]'")),
        )


def downgrade() -> None:
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_column("mcp_server_ids")
