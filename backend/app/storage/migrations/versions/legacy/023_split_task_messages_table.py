"""split task messages into dedicated table

Revision ID: 023
Revises: 022
Create Date: 2026-04-27

"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("agent_id", sa.String(length=50), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("tool_call_id", sa.String(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_messages_task_id"), "task_messages", ["task_id"], unique=False)
    op.create_index(op.f("ix_task_messages_role"), "task_messages", ["role"], unique=False)
    op.create_index(op.f("ix_task_messages_agent_id"), "task_messages", ["agent_id"], unique=False)
    op.create_index(op.f("ix_task_messages_tool_call_id"), "task_messages", ["tool_call_id"], unique=False)
    op.create_index(op.f("ix_task_messages_created_at"), "task_messages", ["created_at"], unique=False)

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    task_columns = {col["name"] for col in inspector.get_columns("tasks")}
    if "messages" in task_columns:
        tasks = conn.execute(sa.text("SELECT id, messages FROM tasks")).fetchall()
        for task_id, raw_messages in tasks:
            if not raw_messages:
                continue
            try:
                parsed = json.loads(raw_messages)
            except (TypeError, ValueError):
                continue
            for raw in parsed:
                metadata = {
                    "event_type": raw.get("event_type"),
                    "event_data": raw.get("event_data"),
                    "checkpoint_id": raw.get("checkpoint_id"),
                    "revision_id": raw.get("revision_id"),
                    "commit_ids": raw.get("commit_ids", []),
                    "is_checkpoint": raw.get("is_checkpoint", False),
                }
                created_at = raw.get("created_at")
                if created_at:
                    try:
                        created_dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                    except ValueError:
                        created_dt = datetime.utcnow()
                else:
                    created_dt = datetime.utcnow()

                conn.execute(
                    sa.text(
                        """
                        INSERT INTO task_messages (
                            id, task_id, role, agent_id, content, tool_calls, tool_call_id, metadata, created_at, updated_at
                        ) VALUES (
                            :id, :task_id, :role, :agent_id, :content, :tool_calls, :tool_call_id, :metadata, :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "id": raw.get("id"),
                        "task_id": task_id,
                        "role": raw.get("role", "assistant"),
                        "agent_id": None,
                        "content": raw.get("content", ""),
                        "tool_calls": "[]",
                        "tool_call_id": None,
                        "metadata": json.dumps(metadata, ensure_ascii=False),
                        "created_at": created_dt,
                        "updated_at": created_dt,
                    },
                )

        with op.batch_alter_table("tasks") as batch_op:
            batch_op.drop_column("messages")


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("messages", sa.String(), nullable=False, server_default="[]"))

    op.drop_index(op.f("ix_task_messages_created_at"), table_name="task_messages")
    op.drop_index(op.f("ix_task_messages_tool_call_id"), table_name="task_messages")
    op.drop_index(op.f("ix_task_messages_agent_id"), table_name="task_messages")
    op.drop_index(op.f("ix_task_messages_role"), table_name="task_messages")
    op.drop_index(op.f("ix_task_messages_task_id"), table_name="task_messages")
    op.drop_table("task_messages")
