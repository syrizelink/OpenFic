"""add skills table

Revision ID: 037
Revises: 036
Create Date: 2026-05-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("skill_id", sa.String(length=100), nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id"),
    )
    op.create_index("ix_skills_skill_id", "skills", ["skill_id"])
    op.create_index("ix_skills_agent_name", "skills", ["agent_name"])
    op.create_index("ix_skills_is_enabled", "skills", ["is_enabled"])


def downgrade() -> None:
    op.drop_index("ix_skills_is_enabled", table_name="skills")
    op.drop_index("ix_skills_agent_name", table_name="skills")
    op.drop_index("ix_skills_skill_id", table_name="skills")
    op.drop_table("skills")
