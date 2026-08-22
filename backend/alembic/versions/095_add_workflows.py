"""add workflows

Revision ID: 095_add_workflows
Revises: 094_add_resources_and_links
Create Date: 2026-08-22
"""
from alembic import op
import sqlalchemy as sa


revision = "095_add_workflows"
down_revision = "094_add_resources_and_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=50), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=True),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workflows")
