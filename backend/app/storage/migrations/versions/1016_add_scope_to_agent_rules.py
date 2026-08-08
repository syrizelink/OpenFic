"""add scope to agent rules

Revision ID: 1016
Revises: 1015
Create Date: 2026-08-08 15:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1016"
down_revision: Union[str, Sequence[str], None] = "1015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_rules") as batch_op:
        batch_op.add_column(
            sa.Column("scope", sa.String(length=16), nullable=False, server_default="global")
        )
        batch_op.add_column(sa.Column("project_id", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("token_count", sa.Integer(), nullable=False, server_default="0")
        )
    op.create_index("ix_agent_rules_project_id", "agent_rules", ["project_id"])
    op.create_index("ix_agent_rules_scope", "agent_rules", ["scope"])


def downgrade() -> None:
    op.drop_index("ix_agent_rules_scope", table_name="agent_rules")
    op.drop_index("ix_agent_rules_project_id", table_name="agent_rules")
    with op.batch_alter_table("agent_rules") as batch_op:
        batch_op.drop_column("token_count")
        batch_op.drop_column("project_id")
        batch_op.drop_column("scope")