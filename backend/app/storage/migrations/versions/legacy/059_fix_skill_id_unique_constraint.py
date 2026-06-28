# -*- coding: utf-8 -*-
"""fix skill_id unique constraint

Revision ID: 059
Revises: 058
Create Date: 2026-06-15

修复 skill_id 的 UNIQUE 约束未被 038 正确移除的问题。
允许空 skill_id 重复，仅对非空 skill_id 强制唯一（应用层校验）。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "059"
down_revision: Union[str, None] = "058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE skills RENAME TO skills_old")
    op.create_table(
        "skills",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("skill_id", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "INSERT INTO skills (id, name, summary, skill_id, agent_name, content, "
        "is_enabled, created_at, updated_at, order_index) "
        "SELECT id, name, summary, skill_id, agent_name, content, "
        "is_enabled, created_at, updated_at, order_index FROM skills_old"
    )
    op.drop_table("skills_old")
    op.create_index("ix_skills_skill_id", "skills", ["skill_id"])
    op.create_index("ix_skills_agent_name", "skills", ["agent_name"])
    op.create_index("ix_skills_is_enabled", "skills", ["is_enabled"])


def downgrade() -> None:
    op.execute("ALTER TABLE skills RENAME TO skills_old")
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
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id"),
    )
    op.execute(
        "INSERT INTO skills (id, name, summary, skill_id, agent_name, content, "
        "is_enabled, created_at, updated_at, order_index) "
        "SELECT id, name, summary, skill_id, agent_name, content, "
        "is_enabled, created_at, updated_at, order_index FROM skills_old"
    )
    op.drop_table("skills_old")
    op.create_index("ix_skills_skill_id", "skills", ["skill_id"])
    op.create_index("ix_skills_agent_name", "skills", ["agent_name"])
    op.create_index("ix_skills_is_enabled", "skills", ["is_enabled"])
