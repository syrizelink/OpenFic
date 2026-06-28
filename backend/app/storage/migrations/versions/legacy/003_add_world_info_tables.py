"""add world info tables

Revision ID: 003
Revises: 002
Create Date: 2025-12-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 world_info 和 world_info_entries 表。"""
    # 创建 world_info 表
    op.create_table(
        "world_info",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_world_info_project_id"),
        "world_info",
        ["project_id"],
        unique=True,
    )

    # 创建 world_info_entries 表
    op.create_table(
        "world_info_entries",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("world_info_id", sa.Text(), nullable=False),
        sa.Column("uid", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("keywords", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["world_info_id"],
            ["world_info.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_world_info_entries_world_info_id"),
        "world_info_entries",
        ["world_info_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_world_info_entries_uid"),
        "world_info_entries",
        ["uid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_world_info_entries_order"),
        "world_info_entries",
        ["order"],
        unique=False,
    )


def downgrade() -> None:
    """删除 world_info 和 world_info_entries 表。"""
    op.drop_index(
        op.f("ix_world_info_entries_order"),
        table_name="world_info_entries",
    )
    op.drop_index(
        op.f("ix_world_info_entries_uid"),
        table_name="world_info_entries",
    )
    op.drop_index(
        op.f("ix_world_info_entries_world_info_id"),
        table_name="world_info_entries",
    )
    op.drop_table("world_info_entries")

    op.drop_index(op.f("ix_world_info_project_id"), table_name="world_info")
    op.drop_table("world_info")
