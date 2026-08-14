"""add_toolkit_and_theme_columns"""

from alembic import op
import sqlalchemy as sa


revision = "093_add_toolkit_and_theme_columns"
down_revision = "092_add_config_to_mcp_servers"
branch_labels = None
depends_on = None


def _has_column(conn, table, column):
    insp = sa.inspect(conn)
    return column in {col["name"] for col in insp.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()

    if not _has_column(conn, "agents", "tools_config"):
        op.add_column("agents", sa.Column("tools_config", sa.JSON(), nullable=True))
    if not _has_column(conn, "agents", "workspace_config"):
        op.add_column("agents", sa.Column("workspace_config", sa.JSON(), nullable=True))
    if not _has_column(conn, "agents", "skills_config"):
        op.add_column("agents", sa.Column("skills_config", sa.JSON(), nullable=True))
    if not _has_column(conn, "agents", "mcp_tools_config"):
        op.add_column("agents", sa.Column("mcp_tools_config", sa.JSON(), nullable=True))
    if not _has_column(conn, "agents", "icon"):
        op.add_column("agents", sa.Column("icon", sa.String(255), nullable=True))
    if not _has_column(conn, "agents", "theme"):
        op.add_column("agents", sa.Column("theme", sa.String(50), nullable=True, server_default="dark-emerald"))

    if not _has_column(conn, "squads", "tools_config"):
        op.add_column("squads", sa.Column("tools_config", sa.JSON(), nullable=True))
    if not _has_column(conn, "squads", "workspace_config"):
        op.add_column("squads", sa.Column("workspace_config", sa.JSON(), nullable=True))
    if not _has_column(conn, "squads", "skills_config"):
        op.add_column("squads", sa.Column("skills_config", sa.JSON(), nullable=True))
    if not _has_column(conn, "squads", "mcp_tools_config"):
        op.add_column("squads", sa.Column("mcp_tools_config", sa.JSON(), nullable=True))
    if not _has_column(conn, "squads", "icon"):
        op.add_column("squads", sa.Column("icon", sa.String(255), nullable=True))
    if not _has_column(conn, "squads", "theme"):
        op.add_column("squads", sa.Column("theme", sa.String(50), nullable=True, server_default="dark-emerald"))

    if not _has_column(conn, "skills", "icon"):
        op.add_column("skills", sa.Column("icon", sa.String(255), nullable=True))
    if not _has_column(conn, "skills", "theme"):
        op.add_column("skills", sa.Column("theme", sa.String(50), nullable=True, server_default="dark-emerald"))

    if not _has_column(conn, "mcp_servers", "icon"):
        op.add_column("mcp_servers", sa.Column("icon", sa.String(255), nullable=True))
    if not _has_column(conn, "mcp_servers", "theme"):
        op.add_column("mcp_servers", sa.Column("theme", sa.String(50), nullable=True, server_default="dark-emerald"))


def downgrade() -> None:
    conn = op.get_bind()

    for table, column in [
        ("mcp_servers", "theme"),
        ("mcp_servers", "icon"),
        ("skills", "theme"),
        ("skills", "icon"),
        ("squads", "theme"),
        ("squads", "mcp_tools_config"),
        ("squads", "skills_config"),
        ("squads", "workspace_config"),
        ("squads", "tools_config"),
        ("agents", "theme"),
        ("agents", "icon"),
        ("agents", "mcp_tools_config"),
        ("agents", "skills_config"),
        ("agents", "workspace_config"),
        ("agents", "tools_config"),
    ]:
        if _has_column(conn, table, column):
            op.drop_column(table, column)
