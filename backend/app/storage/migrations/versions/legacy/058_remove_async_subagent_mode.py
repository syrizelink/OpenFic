"""remove async subagent mode persistence

Revision ID: 058
Revises: 057
Create Date: 2026-06-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "058"
down_revision: Union[str, None] = "057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {
        column["name"] for column in _inspector().get_columns(table_name)
    }


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return index_name in {
        index["name"] for index in _inspector().get_indexes(table_name)
    }


def upgrade() -> None:
    if _has_table("agent_session_queue_items"):
        op.drop_table("agent_session_queue_items")

    if _has_column("agent_child_runs", "dispatch_mode"):
        with op.batch_alter_table("agent_child_runs") as batch_op:
            if _has_index("agent_child_runs", "ix_agent_child_runs_dispatch_mode"):
                batch_op.drop_index("ix_agent_child_runs_dispatch_mode")
            batch_op.drop_column("dispatch_mode")

    if _has_column("agent_child_run_requests", "expect_reply"):
        with op.batch_alter_table("agent_child_run_requests") as batch_op:
            batch_op.drop_column("expect_reply")


def downgrade() -> None:
    if not _has_column("agent_child_runs", "dispatch_mode"):
        with op.batch_alter_table("agent_child_runs") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "dispatch_mode",
                    sa.String(length=20),
                    nullable=False,
                    server_default="sync",
                )
            )
            batch_op.create_index("ix_agent_child_runs_dispatch_mode", ["dispatch_mode"])

    if not _has_column("agent_child_run_requests", "expect_reply"):
        with op.batch_alter_table("agent_child_run_requests") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "expect_reply",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                )
            )

    if not _has_table("agent_session_queue_items"):
        op.create_table(
            "agent_session_queue_items",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("task_id", sa.String(length=64), nullable=False),
            sa.Column("item_type", sa.String(length=50), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        )
        for column_name in [
            "session_id",
            "task_id",
            "item_type",
            "status",
            "seq",
            "created_at",
        ]:
            op.create_index(
                f"ix_agent_session_queue_items_{column_name}",
                "agent_session_queue_items",
                [column_name],
            )
        op.create_index(
            "ix_agent_session_queue_items_session_seq",
            "agent_session_queue_items",
            ["session_id", "seq"],
            unique=True,
        )
