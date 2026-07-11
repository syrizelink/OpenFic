"""remove provider icon upload

Revision ID: 1009
Revises: 1008
Create Date: 2026-07-11 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlmodel import AutoString


revision: str = "1009"
down_revision: Union[str, Sequence[str], None] = "1008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("model_providers") as batch_op:
        batch_op.drop_column("icon_path")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("model_providers") as batch_op:
        batch_op.add_column(
            sa.Column("icon_path", AutoString(length=500), nullable=True)
        )
