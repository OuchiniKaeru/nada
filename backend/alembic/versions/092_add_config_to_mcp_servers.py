"""add_config_to_mcp_servers"""

from alembic import op
import sqlalchemy as sa


revision = "092_add_config_to_mcp_servers"
down_revision = "091_add_leader_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = {col["name"] for col in insp.get_columns("mcp_servers")}
    if "config" not in columns:
        op.add_column(
            "mcp_servers",
            sa.Column("config", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    columns = {col["name"] for col in insp.get_columns("mcp_servers")}
    if "config" in columns:
        op.drop_column("mcp_servers", "config")
