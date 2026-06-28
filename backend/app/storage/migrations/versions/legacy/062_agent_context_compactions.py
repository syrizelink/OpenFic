"""add agent context compactions

Revision ID: 062
Revises: 061
Create Date: 2026-06-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "062"
down_revision: Union[str, None] = "061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_context_compactions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("start_seq", sa.Integer(), nullable=False),
        sa.Column("end_seq", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("source_input_tokens", sa.Integer(), nullable=False),
        sa.Column("summary_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "start_seq >= 0",
            name="ck_agent_context_compactions_start_seq_nonnegative",
        ),
        sa.CheckConstraint(
            "end_seq >= 0",
            name="ck_agent_context_compactions_end_seq_nonnegative",
        ),
        sa.CheckConstraint(
            "source_input_tokens >= 0",
            name="ck_agent_context_compactions_source_input_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "summary_tokens >= 0",
            name="ck_agent_context_compactions_summary_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "start_seq <= end_seq",
            name="ck_agent_context_compactions_valid_range",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_context_compactions_created_at",
        "agent_context_compactions",
        ["created_at"],
    )
    op.create_index(
        "ix_agent_context_compactions_end_seq",
        "agent_context_compactions",
        ["end_seq"],
    )
    op.create_index(
        "ix_agent_context_compactions_project_id",
        "agent_context_compactions",
        ["project_id"],
    )
    op.create_index(
        "ix_agent_context_compactions_session_id",
        "agent_context_compactions",
        ["session_id"],
    )
    op.create_index(
        "ix_agent_context_compactions_session_start_end",
        "agent_context_compactions",
        ["session_id", "start_seq", "end_seq"],
    )
    op.create_index(
        "ix_agent_context_compactions_start_seq",
        "agent_context_compactions",
        ["start_seq"],
    )
    op.create_index(
        "ix_agent_context_compactions_task_id",
        "agent_context_compactions",
        ["task_id"],
    )
    op.create_index(
        "ix_agent_context_compactions_trigger",
        "agent_context_compactions",
        ["trigger"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_context_compactions_trigger",
        table_name="agent_context_compactions",
    )
    op.drop_index(
        "ix_agent_context_compactions_task_id",
        table_name="agent_context_compactions",
    )
    op.drop_index(
        "ix_agent_context_compactions_start_seq",
        table_name="agent_context_compactions",
    )
    op.drop_index(
        "ix_agent_context_compactions_session_start_end",
        table_name="agent_context_compactions",
    )
    op.drop_index(
        "ix_agent_context_compactions_session_id",
        table_name="agent_context_compactions",
    )
    op.drop_index(
        "ix_agent_context_compactions_project_id",
        table_name="agent_context_compactions",
    )
    op.drop_index(
        "ix_agent_context_compactions_end_seq",
        table_name="agent_context_compactions",
    )
    op.drop_index(
        "ix_agent_context_compactions_created_at",
        table_name="agent_context_compactions",
    )
    op.drop_table("agent_context_compactions")
