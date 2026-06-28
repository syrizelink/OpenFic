"""remove world info entry scan and inject columns

Revision ID: 033
Revises: 032
Create Date: 2026-05-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Remove obsolete world info entry scan and injection fields."""
    if _has_column("world_info_entries", "inject_position"):
        op.drop_column("world_info_entries", "inject_position")
    if _has_column("world_info_entries", "scan_depth"):
        op.drop_column("world_info_entries", "scan_depth")


def downgrade() -> None:
    """Restore removed world info entry fields for downgrade."""
    if not _has_column("world_info_entries", "scan_depth"):
        op.add_column(
            "world_info_entries",
            sa.Column("scan_depth", sa.Integer(), nullable=False, server_default="2"),
        )
    if not _has_column("world_info_entries", "inject_position"):
        op.add_column(
            "world_info_entries",
            sa.Column("inject_position", sa.Integer(), nullable=False, server_default="1"),
        )
