"""add persistent subagent thread lifecycle and request queue

Revision ID: 052
Revises: 051
Create Date: 2026-06-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "052"
down_revision: Union[str, None] = "051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_child_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(sa.Column("recycled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_assistant_content", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("last_user_message_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_completed_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_agent_child_runs_is_active", ["is_active"])
        batch_op.create_index("ix_agent_child_runs_recycled_at", ["recycled_at"])
        batch_op.create_index(
            "ix_agent_child_runs_last_user_message_at",
            ["last_user_message_at"],
        )
        batch_op.create_index(
            "ix_agent_child_runs_last_completed_at",
            ["last_completed_at"],
        )

    op.create_table(
        "agent_child_run_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("child_run_id", sa.String(length=64), nullable=False),
        sa.Column("parent_session_id", sa.String(length=64), nullable=False),
        sa.Column("parent_task_id", sa.String(length=64), nullable=False),
        sa.Column("request_kind", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("expect_reply", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("assistant_content", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["child_run_id"], ["agent_child_runs.id"]),
        sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column_name in [
        "child_run_id",
        "parent_session_id",
        "parent_task_id",
        "request_kind",
        "status",
        "seq",
        "created_at",
        "started_at",
        "completed_at",
    ]:
        op.create_index(
            f"ix_agent_child_run_requests_{column_name}",
            "agent_child_run_requests",
            [column_name],
        )
    op.create_index(
        "ix_agent_child_run_requests_child_run_seq",
        "agent_child_run_requests",
        ["child_run_id", "seq"],
        unique=True,
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE agent_definitions
            SET tool_category_keys_json = '["artifact","chapter_read"]',
                updated_at = CURRENT_TIMESTAMP
            WHERE key IN ('clarifier', 'composer', 'reviewer')
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE agent_definitions
            SET tool_category_keys_json = '["artifact","chapter_read","chapter_write"]',
                updated_at = CURRENT_TIMESTAMP
            WHERE key = 'writer'
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_child_run_requests_child_run_seq",
        table_name="agent_child_run_requests",
    )
    for column_name in [
        "completed_at",
        "started_at",
        "created_at",
        "seq",
        "status",
        "request_kind",
        "parent_task_id",
        "parent_session_id",
        "child_run_id",
    ]:
        op.drop_index(
            f"ix_agent_child_run_requests_{column_name}",
            table_name="agent_child_run_requests",
        )
    op.drop_table("agent_child_run_requests")

    with op.batch_alter_table("agent_child_runs") as batch_op:
        batch_op.drop_index("ix_agent_child_runs_last_completed_at")
        batch_op.drop_index("ix_agent_child_runs_last_user_message_at")
        batch_op.drop_index("ix_agent_child_runs_recycled_at")
        batch_op.drop_index("ix_agent_child_runs_is_active")
        batch_op.drop_column("last_completed_at")
        batch_op.drop_column("last_user_message_at")
        batch_op.drop_column("last_assistant_content")
        batch_op.drop_column("recycled_at")
        batch_op.drop_column("is_active")
