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
    """Menyederhanakan entri buku dunia, menghapus kolom mode/entry_type/tags/keywords/memo.

    Entri yang aktif berubah menjadi prompt yang selalu disuntikkan,
    tidak lagi bergantung pada pemicu kata kunci.
    """
    for column in ("mode", "entry_type", "tags", "keywords", "memo"):
        if _has_column("world_info_entries", column):
            op.drop_column("world_info_entries", column)


def downgrade() -> None:
    """Memulihkan kolom entri buku dunia yang telah dihapus."""
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
