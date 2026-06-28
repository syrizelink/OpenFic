"""add agent_rules and agent_memories tables

Revision ID: 039
Revises: 038
Create Date: 2026-05-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_rules_order_index", "agent_rules", ["order_index"])

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_memories_order_index", "agent_memories", ["order_index"])


def downgrade() -> None:
    op.drop_index("ix_agent_memories_order_index", table_name="agent_memories")
    op.drop_table("agent_memories")
    op.drop_index("ix_agent_rules_order_index", table_name="agent_rules")
    op.drop_table("agent_rules")
