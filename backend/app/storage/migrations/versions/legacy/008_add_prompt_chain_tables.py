"""Add prompt chain tables and seed data

Revision ID: 008
Revises: 007
Create Date: 2026-01-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create prompt chain tables and insert seed data."""
    from datetime import UTC, datetime
    from app.core.ids import generate_id

    # 创建 prompt_chains 表
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

    # 创建 prompt_chain_versions 表
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

    # 创建索引
    op.create_index("ix_prompt_chain_versions_prompt_chain_id", "prompt_chain_versions", ["prompt_chain_id"])
    op.create_index("ix_prompt_chain_versions_is_active", "prompt_chain_versions", ["is_active"])

    # 创建 prompt_entries 表
    op.create_table(
        "prompt_entries",
        sa.Column("id", sa.String(), nullable=False),
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

    # 插入种子数据：创作助手 > Chat
    conn = op.get_bind()
    now = datetime.now(UTC)
    
    # 生成ID
    chain_id = generate_id()
    version_id = generate_id()
    version_hash = generate_id()[:8]
    entry1_id = generate_id()
    entry2_id = generate_id()

    # 插入提示词链
    conn.execute(
        sa.text("""
            INSERT INTO prompt_chains (id, mode_name, task_name, agent_name, created_at, updated_at)
            VALUES (:id, :mode_name, :task_name, :agent_name, :created_at, :updated_at)
        """),
        {
            "id": chain_id,
            "mode_name": "创作助手",
            "task_name": "Chat",
            "agent_name": None,
            "created_at": now,
            "updated_at": now,
        }
    )

    # 插入第一个版本 (v1)
    conn.execute(
        sa.text("""
            INSERT INTO prompt_chain_versions 
            (id, prompt_chain_id, version_hash, version_number, parent_version_id, is_active, note, created_at)
            VALUES (:id, :prompt_chain_id, :version_hash, :version_number, :parent_version_id, :is_active, :note, :created_at)
        """),
        {
            "id": version_id,
            "prompt_chain_id": chain_id,
            "version_hash": version_hash,
            "version_number": 1,
            "parent_version_id": None,
            "is_active": True,
            "note": "初始版本",
            "created_at": now,
        }
    )

    # 插入提示词条目1：角色设定
    conn.execute(
        sa.text("""
            INSERT INTO prompt_entries 
            (id, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
            VALUES (:id, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
        """),
        {
            "id": entry1_id,
            "version_id": version_id,
            "name": "角色设定",
            "role": "system",
            "content": "你是一位专业的创意写作助手，擅长帮助作者进行头脑风暴、故事构思和文本润色。",
            "order_index": 0,
            "is_enabled": True,
            "token_count": 30,  # 简单估算
            "created_at": now,
            "updated_at": now,
        }
    )

    # 插入提示词条目2：任务说明
    conn.execute(
        sa.text("""
            INSERT INTO prompt_entries 
            (id, version_id, name, role, content, order_index, is_enabled, token_count, created_at, updated_at)
            VALUES (:id, :version_id, :name, :role, :content, :order_index, :is_enabled, :token_count, :created_at, :updated_at)
        """),
        {
            "id": entry2_id,
            "version_id": version_id,
            "name": "任务说明",
            "role": "user",
            "content": "我正在创作一部小说，需要你的帮助。请根据我的要求提供建议和反馈。",
            "order_index": 1,
            "is_enabled": True,
            "token_count": 28,  # 简单估算
            "created_at": now,
            "updated_at": now,
        }
    )


def downgrade() -> None:
    """Drop prompt chain tables."""
    op.drop_index("ix_prompt_entries_order_index", "prompt_entries")
    op.drop_index("ix_prompt_entries_version_id", "prompt_entries")
    op.drop_table("prompt_entries")
    op.drop_index("ix_prompt_chain_versions_is_active", "prompt_chain_versions")
    op.drop_index("ix_prompt_chain_versions_prompt_chain_id", "prompt_chain_versions")
    op.drop_table("prompt_chain_versions")
    op.drop_table("prompt_chains")
