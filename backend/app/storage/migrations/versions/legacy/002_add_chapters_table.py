"""Add chapters table

Revision ID: 002
Revises: 001
Create Date: 2025-12-24 22:48:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 chapters 表。"""
    op.create_table(
        "chapters",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),  # type: ignore[attr-defined]
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),  # type: ignore[attr-defined]
        sa.Column(
            "title",
            sqlmodel.sql.sqltypes.AutoString(length=200),  # type: ignore[attr-defined]
            nullable=False,
        ),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False),  # type: ignore[attr-defined]
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    # 创建索引
    op.create_index("ix_chapters_project_id", "chapters", ["project_id"])
    op.create_index("ix_chapters_order", "chapters", ["order"])


def downgrade() -> None:
    """删除 chapters 表。"""
    op.drop_index("ix_chapters_order", table_name="chapters")
    op.drop_index("ix_chapters_project_id", table_name="chapters")
    op.drop_table("chapters")
