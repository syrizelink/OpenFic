"""Add quick prompts.

Revision ID: 1030
Revises: 1029
"""

from alembic import op
import sqlalchemy as sa

revision = "1030"
down_revision = "1029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quick_prompts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("command", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
    )
    op.create_index("ix_quick_prompts_project_id", "quick_prompts", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_quick_prompts_project_id", table_name="quick_prompts")
    op.drop_table("quick_prompts")
