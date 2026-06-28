"""add PA/SA agent definitions and child run tables

Revision ID: 051
Revises: 050
Create Date: 2026-06-02

"""

from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "051"
down_revision: Union[str, None] = "050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REMOVED_AGENT_NAMES = ("planner", "auditor", "collector", "yolo", "designer")


def upgrade() -> None:
    _add_llm_visibility()

    op.create_table(
        "agent_definitions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("prompt_agent_name", sa.String(length=50), nullable=False),
        sa.Column("model_id", sa.String(length=100), nullable=True),
        sa.Column("tool_category_keys_json", sa.JSON(), nullable=False),
        sa.Column("skill_policy", sa.String(length=50), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_agent_definitions_key"),
    )
    op.create_index("ix_agent_definitions_key", "agent_definitions", ["key"])
    op.create_index("ix_agent_definitions_kind", "agent_definitions", ["kind"])
    op.create_index("ix_agent_definitions_enabled", "agent_definitions", ["enabled"])
    op.create_index("ix_agent_definitions_order_index", "agent_definitions", ["order_index"])

    op.create_table(
        "agent_child_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("parent_session_id", sa.String(length=64), nullable=False),
        sa.Column("parent_task_id", sa.String(length=64), nullable=False),
        sa.Column("parent_thread_id", sa.String(length=128), nullable=False),
        sa.Column("child_thread_id", sa.String(length=128), nullable=False),
        sa.Column("agent_key", sa.String(length=50), nullable=False),
        sa.Column("dispatch_id", sa.String(length=64), nullable=False),
        sa.Column("tool_call_id", sa.String(length=64), nullable=False),
        sa.Column("dispatch_mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("pending_approval_id", sa.String(length=128), nullable=True),
        sa.Column("pending_approval_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"]),
    )
    for column_name in [
        "parent_session_id",
        "parent_task_id",
        "parent_thread_id",
        "child_thread_id",
        "agent_key",
        "dispatch_id",
        "tool_call_id",
        "dispatch_mode",
        "status",
        "pending_approval_id",
        "started_at",
        "completed_at",
        "created_at",
    ]:
        op.create_index(f"ix_agent_child_runs_{column_name}", "agent_child_runs", [column_name])

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

    _cleanup_old_agent_prompt_and_skill_data()
    _cleanup_old_runtime_sessions()
    _seed_agent_definitions()


def downgrade() -> None:
    op.drop_index(
        "ix_agent_session_queue_items_session_seq",
        table_name="agent_session_queue_items",
    )
    for column_name in [
        "created_at",
        "seq",
        "status",
        "item_type",
        "task_id",
        "session_id",
    ]:
        op.drop_index(
            f"ix_agent_session_queue_items_{column_name}",
            table_name="agent_session_queue_items",
        )
    op.drop_table("agent_session_queue_items")

    for column_name in [
        "created_at",
        "completed_at",
        "started_at",
        "status",
        "pending_approval_id",
        "dispatch_mode",
        "tool_call_id",
        "dispatch_id",
        "agent_key",
        "child_thread_id",
        "parent_thread_id",
        "parent_task_id",
        "parent_session_id",
    ]:
        op.drop_index(f"ix_agent_child_runs_{column_name}", table_name="agent_child_runs")
    op.drop_table("agent_child_runs")

    op.drop_index("ix_agent_definitions_order_index", table_name="agent_definitions")
    op.drop_index("ix_agent_definitions_enabled", table_name="agent_definitions")
    op.drop_index("ix_agent_definitions_kind", table_name="agent_definitions")
    op.drop_index("ix_agent_definitions_key", table_name="agent_definitions")
    op.drop_table("agent_definitions")

    with op.batch_alter_table("agent_run_messages") as batch_op:
        batch_op.drop_index("ix_agent_run_messages_llm_visibility")
        batch_op.drop_column("llm_visibility")


def _add_llm_visibility() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("agent_run_messages")}
    indexes = {index["name"] for index in inspector.get_indexes("agent_run_messages")}

    with op.batch_alter_table("agent_run_messages") as batch_op:
        if "llm_visibility" not in columns:
            batch_op.add_column(
                sa.Column(
                    "llm_visibility",
                    sa.String(length=20),
                    nullable=False,
                    server_default="visible",
                )
            )
        if "ix_agent_run_messages_llm_visibility" not in indexes:
            batch_op.create_index(
                "ix_agent_run_messages_llm_visibility",
                ["llm_visibility"],
            )

    bind.execute(
        sa.text(
            """
            UPDATE agent_run_messages
            SET llm_visibility = 'hidden'
            WHERE display_channel = 'hidden'
              AND message_type != 'message'
            """
        )
    )


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _cleanup_old_agent_prompt_and_skill_data() -> None:
    bind = op.get_bind()
    old_agents = ", ".join(f"'{agent_name}'" for agent_name in REMOVED_AGENT_NAMES)
    bind.execute(
        sa.text(
            f"""
            DELETE FROM prompt_entries
            WHERE version_id IN (
                SELECT id FROM prompt_chain_versions
                WHERE mode_name = 'assistant'
                  AND task_name = 'agent'
                  AND agent_name IN ({old_agents})
            )
            """
        )
    )
    bind.execute(
        sa.text(
            f"""
            DELETE FROM prompt_chain_versions
            WHERE mode_name = 'assistant'
              AND task_name = 'agent'
              AND agent_name IN ({old_agents})
            """
        )
    )
    bind.execute(sa.text(f"DELETE FROM skills WHERE agent_name IN ({old_agents})"))


def _cleanup_old_runtime_sessions() -> None:
    bind = op.get_bind()
    tables = _table_names()
    if "agent_session_checkpoints" in tables:
        bind.execute(
            sa.text(
                """
                DELETE FROM agent_session_checkpoints
                WHERE task_id IN (
                    SELECT id FROM tasks
                    WHERE mode IN ('plan', 'yolo')
                      AND agent_session_id IS NOT NULL
                )
                   OR session_id IN (
                    SELECT agent_session_id FROM tasks
                    WHERE mode IN ('plan', 'yolo')
                      AND agent_session_id IS NOT NULL
                )
                """
            )
        )

    bind.execute(
        sa.text(
            """
            DELETE FROM agent_run_messages
            WHERE task_id IN (
                SELECT id FROM tasks
                WHERE mode IN ('plan', 'yolo')
                  AND agent_session_id IS NOT NULL
            )
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE tasks
            SET mode = 'agent',
                updated_at = CURRENT_TIMESTAMP
            WHERE mode IN ('plan', 'yolo')
              AND agent_session_id IS NOT NULL
            """
        )
    )


def _seed_agent_definitions() -> None:
    now = datetime.now(UTC)
    table = sa.table(
        "agent_definitions",
        sa.column("id", sa.String()),
        sa.column("key", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("kind", sa.String()),
        sa.column("prompt_agent_name", sa.String()),
        sa.column("model_id", sa.String()),
        sa.column("tool_category_keys_json", sa.JSON()),
        sa.column("skill_policy", sa.String()),
        sa.column("metadata_json", sa.JSON()),
        sa.column("enabled", sa.Boolean()),
        sa.column("order_index", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    op.bulk_insert(
        table,
        [
            {
                "id": "agent_definition_primary",
                "key": "primary",
                "display_name": "Primary Agent",
                "kind": "primary",
                "prompt_agent_name": "primary",
                "model_id": None,
                "tool_category_keys_json": [
                    "orchestration",
                    "interaction",
                    "artifact",
                    "chapter_read",
                ],
                "skill_policy": "disabled",
                "metadata_json": {},
                "enabled": True,
                "order_index": 0,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "agent_definition_clarifier",
                "key": "clarifier",
                "display_name": "Clarifier",
                "kind": "subagent",
                "prompt_agent_name": "clarifier",
                "model_id": None,
                "tool_category_keys_json": ["finish", "artifact", "chapter_read"],
                "skill_policy": "enabled_by_agent",
                "metadata_json": {},
                "enabled": True,
                "order_index": 1,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "agent_definition_composer",
                "key": "composer",
                "display_name": "Composer",
                "kind": "subagent",
                "prompt_agent_name": "composer",
                "model_id": None,
                "tool_category_keys_json": ["finish", "artifact", "chapter_read"],
                "skill_policy": "enabled_by_agent",
                "metadata_json": {},
                "enabled": True,
                "order_index": 2,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "agent_definition_writer",
                "key": "writer",
                "display_name": "Writer",
                "kind": "subagent",
                "prompt_agent_name": "writer",
                "model_id": None,
                "tool_category_keys_json": [
                    "finish",
                    "artifact",
                    "chapter_read",
                    "chapter_write",
                ],
                "skill_policy": "enabled_by_agent",
                "metadata_json": {},
                "enabled": True,
                "order_index": 3,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "agent_definition_reviewer",
                "key": "reviewer",
                "display_name": "Reviewer",
                "kind": "subagent",
                "prompt_agent_name": "reviewer",
                "model_id": None,
                "tool_category_keys_json": ["finish", "artifact", "chapter_read"],
                "skill_policy": "enabled_by_agent",
                "metadata_json": {},
                "enabled": True,
                "order_index": 4,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
