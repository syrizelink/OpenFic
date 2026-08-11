"""add color and icon to agent definitions

Revision ID: 1017
Revises: 1016
Create Date: 2026-08-11 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1017"
down_revision: Union[str, Sequence[str], None] = "1016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.add_column(sa.Column("color", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("icon", sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.drop_column("icon")
        batch_op.drop_column("color")
