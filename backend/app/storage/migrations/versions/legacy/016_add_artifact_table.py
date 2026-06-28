"""add artifact table

Revision ID: 016
Revises: 015
Create Date: 2026-02-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add artifacts table for storing tool call results."""
    
    # 创建 artifacts 表
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("agent_session_id", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=True),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("content", sa.String(), nullable=False, server_default=""),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
    )
    
    # 创建 artifacts 表的索引
    op.create_index(op.f("ix_artifacts_project_id"), "artifacts", ["project_id"], unique=False)
    op.create_index(op.f("ix_artifacts_agent_session_id"), "artifacts", ["agent_session_id"], unique=False)
    op.create_index(op.f("ix_artifacts_chapter_id"), "artifacts", ["chapter_id"], unique=False)
    op.create_index(op.f("ix_artifacts_type"), "artifacts", ["type"], unique=False)


def downgrade() -> None:
    """Remove artifacts table."""
    
    # 删除 artifacts 表的索引
    op.drop_index(op.f("ix_artifacts_type"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_chapter_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_agent_session_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_project_id"), table_name="artifacts")
    
    # 删除 artifacts 表
    op.drop_table("artifacts")