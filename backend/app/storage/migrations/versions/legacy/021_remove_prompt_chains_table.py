"""Remove prompt_chains table, add mode/task/agent fields to prompt_chain_versions

Revision ID: 021
Revises: 020
Create Date: 2026-04-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove prompt_chains table and migrate data to prompt_chain_versions."""
    conn = op.get_bind()
    
    # Step 1: 删除所有 prompt-chain 相关表的数据
    conn.execute(sa.text("DELETE FROM prompt_entries"))
    conn.execute(sa.text("DELETE FROM prompt_chain_versions"))
    conn.execute(sa.text("DELETE FROM prompt_chains"))
    
    # Step 2: 使用批处理模式重建 prompt_chain_versions 表
    # 删除旧表，创建新表
    op.drop_table("prompt_entries")
    op.drop_index("ix_prompt_chain_versions_is_active", "prompt_chain_versions")
    op.drop_index("ix_prompt_chain_versions_prompt_chain_id", "prompt_chain_versions")
    op.drop_table("prompt_chain_versions")
    op.drop_table("prompt_chains")
    
    # 创建新的 prompt_chain_versions 表（包含新字段）
    op.create_table(
        "prompt_chain_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("mode_name", sa.String(length=100), nullable=False),
        sa.Column("task_name", sa.String(length=100), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=True),
        sa.Column("version_hash", sa.String(length=8), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_version_id"], ["prompt_chain_versions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("version_hash"),
    )
    
    # 创建索引
    op.create_index("ix_prompt_chain_versions_mode_task", "prompt_chain_versions", ["mode_name", "task_name"])
    op.create_index("ix_prompt_chain_versions_is_active", "prompt_chain_versions", ["is_active"])
    
    # 重新创建 prompt_entries 表
    op.create_table(
        "prompt_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("uid", sa.String(), nullable=False),
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["version_id"], ["prompt_chain_versions.id"], ondelete="CASCADE"),
    )
    
    # 创建索引
    op.create_index("ix_prompt_entries_version_id", "prompt_entries", ["version_id"])
    op.create_index("ix_prompt_entries_order_index", "prompt_entries", ["order_index"])


def downgrade() -> None:
    """Recreate prompt_chains table and migrate data back."""
    conn = op.get_bind()
    
    # 删除所有数据
    conn.execute(sa.text("DELETE FROM prompt_entries"))
    conn.execute(sa.text("DELETE FROM prompt_chain_versions"))
    
    # 删除表
    op.drop_index("ix_prompt_entries_order_index", "prompt_entries")
    op.drop_index("ix_prompt_entries_version_id", "prompt_entries")
    op.drop_table("prompt_entries")
    op.drop_index("ix_prompt_chain_versions_is_active", "prompt_chain_versions")
    op.drop_index("ix_prompt_chain_versions_mode_task", "prompt_chain_versions")
    op.drop_table("prompt_chain_versions")
    
    # 重新创建 prompt_chains 表
    op.create_table(
        "prompt_chains",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("mode_name", sa.String(length=100), nullable=False),
        sa.Column("task_name", sa.String(length=100), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # 重新创建 prompt_chain_versions 表
    op.create_table(
        "prompt_chain_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("prompt_chain_id", sa.String(), nullable=False),
        sa.Column("version_hash", sa.String(length=8), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["prompt_chain_id"], ["prompt_chains.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_version_id"], ["prompt_chain_versions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("version_hash"),
    )
    
    op.create_index("ix_prompt_chain_versions_prompt_chain_id", "prompt_chain_versions", ["prompt_chain_id"])
    op.create_index("ix_prompt_chain_versions_is_active", "prompt_chain_versions", ["is_active"])
    
    # 重新创建 prompt_entries 表
    op.create_table(
        "prompt_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("uid", sa.String(), nullable=False),
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["version_id"], ["prompt_chain_versions.id"], ondelete="CASCADE"),
    )
    
    op.create_index("ix_prompt_entries_version_id", "prompt_entries", ["version_id"])
    op.create_index("ix_prompt_entries_order_index", "prompt_entries", ["order_index"])
