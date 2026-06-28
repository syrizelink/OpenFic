"""add agent_run_messages table

Revision ID: 040
Revises: 039
Create Date: 2026-05-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_run_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("agent_id", sa.String(length=50), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("tool_calls", sa.Text(), nullable=True),
        sa.Column("tool_call_id", sa.String(length=64), nullable=True),
        sa.Column("tool_name", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
    )
    op.create_index("ix_agent_run_messages_session_id", "agent_run_messages", ["session_id"])
    op.create_index("ix_agent_run_messages_task_id", "agent_run_messages", ["task_id"])
    op.create_index("ix_agent_run_messages_project_id", "agent_run_messages", ["project_id"])
    op.create_index("ix_agent_run_messages_role", "agent_run_messages", ["role"])
    op.create_index("ix_agent_run_messages_agent_id", "agent_run_messages", ["agent_id"])
    op.create_index("ix_agent_run_messages_tool_call_id", "agent_run_messages", ["tool_call_id"])
    op.create_index("ix_agent_run_messages_status", "agent_run_messages", ["status"])
    op.create_index("ix_agent_run_messages_seq", "agent_run_messages", ["seq"])
    op.create_index("ix_agent_run_messages_created_at", "agent_run_messages", ["created_at"])
    op.create_index(
        "ix_agent_run_messages_session_seq",
        "agent_run_messages",
        ["session_id", "seq"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_run_messages_session_seq", table_name="agent_run_messages")
    op.drop_index("ix_agent_run_messages_created_at", table_name="agent_run_messages")
    op.drop_index("ix_agent_run_messages_seq", table_name="agent_run_messages")
    op.drop_index("ix_agent_run_messages_status", table_name="agent_run_messages")
    op.drop_index("ix_agent_run_messages_tool_call_id", table_name="agent_run_messages")
    op.drop_index("ix_agent_run_messages_agent_id", table_name="agent_run_messages")
    op.drop_index("ix_agent_run_messages_role", table_name="agent_run_messages")
    op.drop_index("ix_agent_run_messages_project_id", table_name="agent_run_messages")
    op.drop_index("ix_agent_run_messages_task_id", table_name="agent_run_messages")
    op.drop_index("ix_agent_run_messages_session_id", table_name="agent_run_messages")
    op.drop_table("agent_run_messages")
