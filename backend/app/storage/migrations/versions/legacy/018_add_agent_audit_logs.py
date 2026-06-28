"""add agent_audit_logs table

Revision ID: 018
Revises: 017
Create Date: 2026-04-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017_link_task_messages_to_checkpoints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add agent_audit_logs table for Agent auditing."""

    op.create_table(
        "agent_audit_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=True),
        sa.Column("revision_id", sa.String(), nullable=True),
        sa.Column("agent_node", sa.String(length=50), nullable=False),
        sa.Column("call_sequence", sa.Integer(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_provider", sa.String(length=50), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("request_messages", sa.String(), nullable=True),
        sa.Column("response_content", sa.String(), nullable=True),
        sa.Column("response_tool_calls", sa.String(), nullable=True),
        sa.Column("tool_call_results", sa.String(), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_output", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("first_token_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_type", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("error_status_code", sa.Integer(), nullable=True),
        sa.Column("tool_calls_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "tool_calls_success_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "tool_calls_failed_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("extra_data", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
    )

    op.create_index(
        op.f("ix_agent_audit_logs_task_id"),
        "agent_audit_logs",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_audit_logs_session_id"),
        "agent_audit_logs",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_audit_logs_project_id"),
        "agent_audit_logs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_audit_logs_revision_id"),
        "agent_audit_logs",
        ["revision_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_audit_logs_created_at"),
        "agent_audit_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_audit_logs_model_id"),
        "agent_audit_logs",
        ["model_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_audit_logs_status"), "agent_audit_logs", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_agent_audit_logs_agent_node"),
        "agent_audit_logs",
        ["agent_node"],
        unique=False,
    )


def downgrade() -> None:
    """Remove agent_audit_logs table."""

    op.drop_index(op.f("ix_agent_audit_logs_agent_node"), table_name="agent_audit_logs")
    op.drop_index(op.f("ix_agent_audit_logs_status"), table_name="agent_audit_logs")
    op.drop_index(op.f("ix_agent_audit_logs_model_id"), table_name="agent_audit_logs")
    op.drop_index(op.f("ix_agent_audit_logs_created_at"), table_name="agent_audit_logs")
    op.drop_index(
        op.f("ix_agent_audit_logs_revision_id"), table_name="agent_audit_logs"
    )
    op.drop_index(op.f("ix_agent_audit_logs_project_id"), table_name="agent_audit_logs")
    op.drop_index(op.f("ix_agent_audit_logs_session_id"), table_name="agent_audit_logs")
    op.drop_index(op.f("ix_agent_audit_logs_task_id"), table_name="agent_audit_logs")

    op.drop_table("agent_audit_logs")
