"""Update provider icon fields

Revision ID: 007
Revises: 006
Create Date: 2026-01-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update model_providers table to use icon_path instead of icon_type/custom_icon."""
    # SQLite tidak mendukung penghapusan kolom secara langsung, tabel perlu dibangun ulang
    with op.batch_alter_table("model_providers") as batch_op:
        batch_op.add_column(sa.Column("icon_path", sa.String(length=500), nullable=True))
    
    # Migrasi data dapat dilakukan di sini, tetapi karena logikanya berubah, sementara dilewati
    
    # Menghapus kolom lama
    with op.batch_alter_table("model_providers") as batch_op:
        batch_op.drop_column("icon_type")
        batch_op.drop_column("custom_icon")


def downgrade() -> None:
    """Revert icon fields changes."""
    with op.batch_alter_table("model_providers") as batch_op:
        batch_op.add_column(sa.Column("icon_type", sa.String(length=20), nullable=False, server_default="default"))
        batch_op.add_column(sa.Column("custom_icon", sa.String(length=10000), nullable=False, server_default=""))
        batch_op.drop_column("icon_path")
