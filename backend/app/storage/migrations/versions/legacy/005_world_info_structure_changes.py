"""world_info_structure_changes

Revision ID: 005
Revises: 004
Create Date: 2026-01-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Menambahkan kolom baru untuk buku dunia dan entri."""
    # Menambahkan kolom description pada tabel world_info
    op.add_column(
        "world_info",
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )

    # Menambahkan kolom baru pada tabel world_info_entries
    op.add_column(
        "world_info_entries",
        sa.Column("memo", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "world_info_entries",
        sa.Column("tags", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "world_info_entries",
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="keyword"),
    )
    op.add_column(
        "world_info_entries",
        sa.Column("scan_depth", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "world_info_entries",
        sa.Column("entry_type", sa.String(length=20), nullable=False, server_default="setting"),
    )
    op.add_column(
        "world_info_entries",
        sa.Column("inject_position", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    """Menghapus kolom baru pada buku dunia dan entri."""
    # Menghapus kolom baru pada tabel world_info_entries
    op.drop_column("world_info_entries", "inject_position")
    op.drop_column("world_info_entries", "entry_type")
    op.drop_column("world_info_entries", "scan_depth")
    op.drop_column("world_info_entries", "mode")
    op.drop_column("world_info_entries", "tags")
    op.drop_column("world_info_entries", "memo")

    # Menghapus kolom description pada tabel world_info
    op.drop_column("world_info", "description")
