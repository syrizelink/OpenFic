"""make_project_id_nullable

Membuat kolom project_id pada tabel world_info dapat kosong, agar buku dunia mandiri dapat dibuat.

Revision ID: 004
Revises: 003
Create Date: 2024-12-29
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Mengubah project_id menjadi kolom yang dapat kosong."""
    # SQLite tidak mendukung modifikasi kolom secara langsung, tabel perlu dibangun ulang
    # Namun untuk kasus ini, SQLite mengizinkan nilai NULL walau kolom didefinisikan NOT NULL
    # karena SQLModel menangani logika ini di lapisan Python
    # Di sini kita memakai batch_alter_table agar perubahan aman
    with op.batch_alter_table("world_info") as batch_op:
        batch_op.alter_column(
            "project_id",
            nullable=True,
        )


def downgrade() -> None:
    """Mengubah project_id kembali menjadi kolom yang tidak boleh kosong."""
    with op.batch_alter_table("world_info") as batch_op:
        batch_op.alter_column(
            "project_id",
            nullable=False,
        )
