"""add audit token cache

Revision ID: 026
Revises: 025
Create Date: 2026-05-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "agent_audit_logs" not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns("agent_audit_logs")}


def upgrade() -> None:
    """Store provider-reported cached input token count."""
    if "token_cache" not in _existing_columns():
        op.add_column(
            "agent_audit_logs",
            sa.Column("token_cache", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    """Remove cached token count from audit logs."""
    if "token_cache" in _existing_columns():
        op.drop_column("agent_audit_logs", "token_cache")
