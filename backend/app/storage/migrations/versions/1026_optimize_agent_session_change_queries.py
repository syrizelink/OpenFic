"""Add indexes used by agent session transcript and change projections.

Revision ID: 1026
Revises: 1025
Create Date: 2026-10-08
"""

from typing import Sequence, Union

from alembic import op


revision: str = "1026"
down_revision: Union[str, Sequence[str], None] = "1025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES: tuple[tuple[str, str, list[str]], ...] = (
    (
        "ix_agent_run_messages_session_id_seq",
        "agent_run_messages",
        ["session_id", "seq"],
    ),
    (
        "ix_agent_child_runs_parent_session_id_created_at",
        "agent_child_runs",
        ["parent_session_id", "created_at"],
    ),
    (
        "ix_agent_child_runs_parent_session_id_parent_revision_id",
        "agent_child_runs",
        ["parent_session_id", "parent_revision_id"],
    ),
    (
        "ix_agent_child_run_requests_child_run_id_seq",
        "agent_child_run_requests",
        ["child_run_id", "seq"],
    ),
    (
        "ix_revisions_agent_session_id_type_seq_created_at",
        "revisions",
        ["agent_session_id", "revision_type", "user_message_seq", "created_at"],
    ),
)


def upgrade() -> None:
    for name, table_name, columns in INDEXES:
        op.create_index(name, table_name, columns, unique=False)


def downgrade() -> None:
    for name, table_name, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table_name)
