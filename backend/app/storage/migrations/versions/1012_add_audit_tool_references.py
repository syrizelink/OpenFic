"""add audit tool references

Revision ID: 1012
Revises: 1011
Create Date: 2026-07-16 22:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1012"
down_revision: Union[str, Sequence[str], None] = "1011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Store the tool definitions bound to each audited model request."""
    with op.batch_alter_table("agent_audit_logs") as batch_op:
        batch_op.add_column(sa.Column("tool_references", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove stored tool definitions from audit logs."""
    with op.batch_alter_table("agent_audit_logs") as batch_op:
        batch_op.drop_column("tool_references")
