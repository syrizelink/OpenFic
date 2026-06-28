"""add version control tables

Revision ID: 015
Revises: 014
Create Date: 2026-02-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add revisions and commits tables for version control."""
    
    # 1. 创建 revisions 表
    op.create_table(
        "revisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("agent_session_id", sa.String(), nullable=True),
        sa.Column("is_checkpoint", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("project_snapshot_title", sa.String(length=200), nullable=False),
        sa.Column("project_snapshot_description", sa.String(), nullable=True),
        sa.Column("project_snapshot_word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("project_snapshot_chapter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )
    
    # 创建 revisions 表的索引
    op.create_index(op.f("ix_revisions_project_id"), "revisions", ["project_id"], unique=False)
    op.create_index(op.f("ix_revisions_is_checkpoint"), "revisions", ["is_checkpoint"], unique=False)
    op.create_index(op.f("ix_revisions_created_at"), "revisions", ["created_at"], unique=False)
    
    # 2. 创建 commits 表
    op.create_table(
        "commits",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("revision_id", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("snapshot_title", sa.String(length=200), nullable=True),
        sa.Column("snapshot_content", sa.String(), nullable=True),
        sa.Column("snapshot_word_count", sa.Integer(), nullable=True),
        sa.Column("snapshot_order", sa.Integer(), nullable=True),
        sa.Column("new_title", sa.String(length=200), nullable=True),
        sa.Column("new_content", sa.String(), nullable=True),
        sa.Column("new_word_count", sa.Integer(), nullable=True),
        sa.Column("new_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
    )
    
    # 创建 commits 表的索引
    op.create_index(op.f("ix_commits_revision_id"), "commits", ["revision_id"], unique=False)
    op.create_index(op.f("ix_commits_chapter_id"), "commits", ["chapter_id"], unique=False)


def downgrade() -> None:
    """Remove version control tables."""
    
    # 删除 commits 表的索引
    op.drop_index(op.f("ix_commits_chapter_id"), table_name="commits")
    op.drop_index(op.f("ix_commits_revision_id"), table_name="commits")
    
    # 删除 commits 表
    op.drop_table("commits")
    
    # 删除 revisions 表的索引
    op.drop_index(op.f("ix_revisions_created_at"), table_name="revisions")
    op.drop_index(op.f("ix_revisions_is_checkpoint"), table_name="revisions")
    op.drop_index(op.f("ix_revisions_project_id"), table_name="revisions")
    
    # 删除 revisions 表
    op.drop_table("revisions")