"""add order_index to skills table and allow duplicate empty skill_id

Revision ID: 038
Revises: 037
Create Date: 2026-05-17

Mengizinkan skill_id kosong (tidak wajib diisi saat pembuatan), dan menambahkan
order_index untuk mendukung pengurutan seret.
Menghapus constraint UNIQUE pada skill_id, digantikan validasi keunikan
skill_id non-kosong di lapisan aplikasi.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Membangun ulang tabel memakai batch mode: menambahkan kolom order_index
    # dan menghapus constraint unique pada skill_id
    with op.batch_alter_table(
        "skills",
        schema=None,
        recreate="always",
        table_args=(
            sa.PrimaryKeyConstraint("id"),
        ),
    ) as batch_op:
        batch_op.add_column(
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "skills",
        schema=None,
        recreate="always",
        table_args=(
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("skill_id"),
        ),
    ) as batch_op:
        batch_op.drop_column("order_index")
