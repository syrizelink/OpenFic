"""simplify world info entries

Revision ID: 073
Revises: 072
Create Date: 2026-06-26 11:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "073"
down_revision: Union[str, None] = "072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    """精简世界书条目，移除 mode/entry_type/tags/keywords/memo 列。

    启用条目改为常驻注入提示词，不再依赖关键词触发。
    """
    for column in ("mode", "entry_type", "tags", "keywords", "memo"):
        if _has_column("world_info_entries", column):
            op.drop_column("world_info_entries", column)


def downgrade() -> None:
    """恢复被移除的世界书条目列。"""
    if not _has_column("world_info_entries", "memo"):
        op.add_column(
            "world_info_entries",
            sa.Column("memo", sa.Text(), nullable=False, server_default=""),
        )
    if not _has_column("world_info_entries", "tags"):
        op.add_column(
            "world_info_entries",
            sa.Column("tags", sa.Text(), nullable=False, server_default="[]"),
        )
    if not _has_column("world_info_entries", "keywords"):
        op.add_column(
            "world_info_entries",
            sa.Column("keywords", sa.Text(), nullable=False, server_default="[]"),
        )
    if not _has_column("world_info_entries", "entry_type"):
        op.add_column(
            "world_info_entries",
            sa.Column("entry_type", sa.String(length=20), nullable=False, server_default="setting"),
        )
    if not _has_column("world_info_entries", "mode"):
        op.add_column(
            "world_info_entries",
            sa.Column("mode", sa.String(length=20), nullable=False, server_default="keyword"),
        )
