"""add indexes for dashboard filters and date ranges

Revision ID: 1021
Revises: 1020
Create Date: 2026-08-27
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "1021"
down_revision: Union[str, Sequence[str], None] = "1020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AUDIT_INDEXES: tuple[tuple[str, list[str]], ...] = (
    ("ix_agent_audit_logs_project_id_created_at", ["project_id", "created_at"]),
    ("ix_agent_audit_logs_model_provider_created_at", ["model_provider", "created_at"]),
    ("ix_agent_audit_logs_model_id_created_at", ["model_id", "created_at"]),
    ("ix_agent_audit_logs_operation_created_at", ["operation", "created_at"]),
    ("ix_agent_audit_logs_task_id_created_at", ["task_id", "created_at"]),
    ("ix_agent_audit_logs_session_id_created_at", ["session_id", "created_at"]),
)

WRITING_ACTIVITY_INDEXES: tuple[tuple[str, list[str]], ...] = (
    (
        "ix_writing_activity_events_project_id_created_at",
        ["project_id", "created_at"],
    ),
    ("ix_writing_activity_events_source_created_at", ["source", "created_at"]),
    (
        "ix_writing_activity_events_project_source_created_at",
        ["project_id", "source", "created_at"],
    ),
)


def upgrade() -> None:
    """Add indexes used by dashboard filtering and date ranges."""
    for name, columns in AUDIT_INDEXES:
        op.create_index(name, "agent_audit_logs", columns, unique=False)
    for name, columns in WRITING_ACTIVITY_INDEXES:
        op.create_index(name, "writing_activity_events", columns, unique=False)


def downgrade() -> None:
    """Remove dashboard query indexes."""
    for name, _columns in reversed(WRITING_ACTIVITY_INDEXES):
        op.drop_index(name, table_name="writing_activity_events")
    for name, _columns in reversed(AUDIT_INDEXES):
        op.drop_index(name, table_name="agent_audit_logs")
