"""add resources and resource_links

Revision ID: 094
Revises: 093_add_toolkit_and_theme_columns
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "094_add_resources_and_links"
down_revision = "093_add_toolkit_and_theme_columns"
branch_labels = None
depends_on = None

# SQLite 互換のため batch_alter_table を使用(CREATE TABLE のみなので通常不要だが統一)。


def upgrade() -> None:
    op.create_table(
        "resources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=50), nullable=True),
        sa.Column("config_format", sa.String(length=10), nullable=False),
        sa.Column("config_path", sa.String(length=512), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resources_type"), "resources", ["type"], unique=False)

    op.create_table(
        "resource_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("parent_type", sa.String(length=50), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resource_links_parent_type"), "resource_links", ["parent_type"], unique=False)
    op.create_index(op.f("ix_resource_links_parent_id"), "resource_links", ["parent_id"], unique=False)
    op.create_index(op.f("ix_resource_links_resource_id"), "resource_links", ["resource_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_resource_links_resource_id"), table_name="resource_links")
    op.drop_index(op.f("ix_resource_links_parent_id"), table_name="resource_links")
    op.drop_index(op.f("ix_resource_links_parent_type"), table_name="resource_links")
    op.drop_table("resource_links")
    op.drop_index(op.f("ix_resources_type"), table_name="resources")
    op.drop_table("resources")
