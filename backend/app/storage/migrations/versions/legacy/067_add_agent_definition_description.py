"""add agent_definition description column

Revision ID: 067
Revises: 066
Create Date: 2026-06-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "067"
down_revision: Union[str, None] = "066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "description",
                sa.Text(),
                nullable=False,
                server_default="",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.drop_column("description")
