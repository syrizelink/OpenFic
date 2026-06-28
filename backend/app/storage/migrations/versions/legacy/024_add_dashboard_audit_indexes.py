"""add dashboard audit indexes

Revision ID: 024
Revises: 023
Create Date: 2026-05-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES: tuple[tuple[str, list[str]], ...] = (
    ("ix_agent_audit_logs_created_at", ["created_at"]),
    ("ix_agent_audit_logs_model_provider", ["model_provider"]),
    ("ix_agent_audit_logs_project_id_created_at", ["project_id", "created_at"]),
    ("ix_agent_audit_logs_model_provider_created_at", ["model_provider", "created_at"]),
    ("ix_agent_audit_logs_model_id_created_at", ["model_id", "created_at"]),
    ("ix_agent_audit_logs_agent_node_created_at", ["agent_node", "created_at"]),
    ("ix_agent_audit_logs_status_created_at", ["status", "created_at"]),
    ("ix_agent_audit_logs_task_id_created_at", ["task_id", "created_at"]),
    ("ix_agent_audit_logs_session_id_created_at", ["session_id", "created_at"]),
)


def _existing_indexes() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "agent_audit_logs" not in inspector.get_table_names():
        return set()
    return {
        name
        for index in inspector.get_indexes("agent_audit_logs")
        if isinstance(name := index["name"], str)
    }


def upgrade() -> None:
    """Add indexes used by dashboard filtering and record sorting."""
    existing = _existing_indexes()
    for name, columns in INDEXES:
        if name not in existing:
            op.create_index(name, "agent_audit_logs", columns, unique=False)


def downgrade() -> None:
    """Remove dashboard-specific audit indexes."""
    existing = _existing_indexes()
    for name, _columns in reversed(INDEXES):
        if name in existing:
            op.drop_index(name, table_name="agent_audit_logs")
