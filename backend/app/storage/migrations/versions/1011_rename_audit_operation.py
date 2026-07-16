"""rename audit agent node to operation

Revision ID: 1011
Revises: 1010
Create Date: 2026-07-15 20:45:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1011"
down_revision: Union[str, Sequence[str], None] = "1010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename the operation column and add audit categories."""
    op.drop_index("ix_agent_audit_logs_agent_node", table_name="agent_audit_logs")
    op.alter_column(
        "agent_audit_logs",
        "agent_node",
        new_column_name="operation",
    )
    op.add_column(
        "agent_audit_logs",
        sa.Column("category", sa.String(length=50), nullable=True),
    )
    op.execute(sa.text("UPDATE agent_audit_logs SET category = 'agent'"))
    with op.batch_alter_table("agent_audit_logs") as batch_op:
        batch_op.alter_column("category", existing_type=sa.String(length=50), nullable=False)
    op.create_index("ix_agent_audit_logs_operation", "agent_audit_logs", ["operation"], unique=False)
    op.create_index("ix_agent_audit_logs_category", "agent_audit_logs", ["category"], unique=False)


def downgrade() -> None:
    """Restore the legacy Agent-specific operation name."""
    op.drop_index("ix_agent_audit_logs_category", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_operation", table_name="agent_audit_logs")
    with op.batch_alter_table("agent_audit_logs") as batch_op:
        batch_op.drop_column("category")
    op.alter_column(
        "agent_audit_logs",
        "operation",
        new_column_name="agent_node",
    )
    op.create_index(
        "ix_agent_audit_logs_agent_node",
        "agent_audit_logs",
        ["agent_node"],
        unique=False,
    )
