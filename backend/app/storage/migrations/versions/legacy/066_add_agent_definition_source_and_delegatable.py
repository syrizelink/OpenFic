"""add agent_definition source and delegatable_agents columns

Revision ID: 066
Revises: 065
Create Date: 2026-06-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "066"
down_revision: Union[str, None] = "065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source",
                sa.String(length=20),
                nullable=False,
                server_default="builtin",
            )
        )
        batch_op.add_column(
            sa.Column(
                "delegatable_agents",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    op.create_index("ix_agent_definitions_source", "agent_definitions", ["source"])


def downgrade() -> None:
    op.drop_index("ix_agent_definitions_source", table_name="agent_definitions")

    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.drop_column("delegatable_agents")
        batch_op.drop_column("source")
