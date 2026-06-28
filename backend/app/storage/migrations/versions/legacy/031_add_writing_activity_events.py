"""add writing activity events

Revision ID: 031
Revises: 030
Create Date: 2026-05-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create writing activity event table for dashboard statistics."""
    op.create_table(
        "writing_activity_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=True),
        sa.Column("chapter_title", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("old_word_count", sa.Integer(), nullable=False),
        sa.Column("new_word_count", sa.Integer(), nullable=False),
        sa.Column("word_delta", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.String(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("agent_session_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_writing_activity_events_created_at", "writing_activity_events", ["created_at"])
    op.create_index("ix_writing_activity_events_project_id", "writing_activity_events", ["project_id"])
    op.create_index("ix_writing_activity_events_chapter_id", "writing_activity_events", ["chapter_id"])
    op.create_index("ix_writing_activity_events_source", "writing_activity_events", ["source"])
    op.create_index("ix_writing_activity_events_operation", "writing_activity_events", ["operation"])
    op.create_index("ix_writing_activity_events_revision_id", "writing_activity_events", ["revision_id"])
    op.create_index("ix_writing_activity_events_task_id", "writing_activity_events", ["task_id"])
    op.create_index("ix_writing_activity_events_agent_session_id", "writing_activity_events", ["agent_session_id"])
    op.create_index(
        "ix_writing_activity_events_project_id_created_at",
        "writing_activity_events",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_writing_activity_events_source_created_at",
        "writing_activity_events",
        ["source", "created_at"],
    )


def downgrade() -> None:
    """Drop writing activity event table."""
    op.drop_index("ix_writing_activity_events_source_created_at", table_name="writing_activity_events")
    op.drop_index("ix_writing_activity_events_project_id_created_at", table_name="writing_activity_events")
    op.drop_index("ix_writing_activity_events_agent_session_id", table_name="writing_activity_events")
    op.drop_index("ix_writing_activity_events_task_id", table_name="writing_activity_events")
    op.drop_index("ix_writing_activity_events_revision_id", table_name="writing_activity_events")
    op.drop_index("ix_writing_activity_events_operation", table_name="writing_activity_events")
    op.drop_index("ix_writing_activity_events_source", table_name="writing_activity_events")
    op.drop_index("ix_writing_activity_events_chapter_id", table_name="writing_activity_events")
    op.drop_index("ix_writing_activity_events_project_id", table_name="writing_activity_events")
    op.drop_index("ix_writing_activity_events_created_at", table_name="writing_activity_events")
    op.drop_table("writing_activity_events")
