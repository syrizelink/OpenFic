"""drop skill order_index column

Revision ID: 068
Revises: 067
Create Date: 2026-06-24

Menghapus order_index pada tabel skills, daftar skill berubah menjadi urutan
pembuatan tetap dan tidak lagi mendukung pengurutan manual.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "068"
down_revision: Union[str, None] = "067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("skills") as batch_op:
        batch_op.drop_column("order_index")


def downgrade() -> None:
    with op.batch_alter_table("skills") as batch_op:
        batch_op.add_column(
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0")
        )
