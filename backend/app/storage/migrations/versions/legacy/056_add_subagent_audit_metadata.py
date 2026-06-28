"""add subagent audit metadata

Revision ID: 056
Revises: 055_remove_builtin_agent_definition_rows
Create Date: 2026-06-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "056"
down_revision: Union[str, None] = "055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_audit_logs",
        sa.Column("parent_session_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "agent_audit_logs",
        sa.Column("child_run_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_agent_audit_logs_parent_session_id"),
        "agent_audit_logs",
        ["parent_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_audit_logs_child_run_id"),
        "agent_audit_logs",
        ["child_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_audit_logs_child_run_id"),
        table_name="agent_audit_logs",
    )
    op.drop_index(
        op.f("ix_agent_audit_logs_parent_session_id"),
        table_name="agent_audit_logs",
    )
    op.drop_column("agent_audit_logs", "child_run_id")
    op.drop_column("agent_audit_logs", "parent_session_id")
