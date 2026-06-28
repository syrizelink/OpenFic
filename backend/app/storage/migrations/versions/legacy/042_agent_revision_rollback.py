"""agent revision rollback anchors

Revision ID: 042
Revises: 041
Create Date: 2026-05-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "agent_session_checkpoints" in tables:
        op.drop_table("agent_session_checkpoints")

    if "tasks" in tables:
        task_columns = _column_names(bind, "tasks")
        assignments = []
        if "current_revision_id" in task_columns:
            assignments.append("current_revision_id = NULL")
        if "current_message_id" in task_columns:
            assignments.append("current_message_id = NULL")
        if assignments:
            bind.execute(sa.text(f"UPDATE tasks SET {', '.join(assignments)}"))

    if "agent_audit_logs" in tables and "revision_id" in _column_names(bind, "agent_audit_logs"):
        bind.execute(sa.text("UPDATE agent_audit_logs SET revision_id = NULL"))
    if "writing_activity_events" in tables and "revision_id" in _column_names(bind, "writing_activity_events"):
        bind.execute(sa.text("UPDATE writing_activity_events SET revision_id = NULL"))

    if "revision_chapter_snapshots" in tables:
        bind.execute(sa.text("DELETE FROM revision_chapter_snapshots"))
    if "commits" in tables:
        bind.execute(sa.text("DELETE FROM commits"))
    if "revisions" in tables:
        bind.execute(sa.text("DELETE FROM revisions"))

    revision_columns = _column_names(bind, "revisions")
    revision_indexes = _index_names(bind, "revisions")
    with op.batch_alter_table("revisions") as batch_op:
        if "user_message_id" not in revision_columns:
            batch_op.add_column(sa.Column("user_message_id", sa.String(), nullable=True))
        if "ix_revisions_user_message_id" not in revision_indexes:
            batch_op.create_index("ix_revisions_user_message_id", ["user_message_id"])
        if "user_message_seq" not in revision_columns:
            batch_op.add_column(sa.Column("user_message_seq", sa.Integer(), nullable=True))
        if "ix_revisions_user_message_seq" not in revision_indexes:
            batch_op.create_index("ix_revisions_user_message_seq", ["user_message_seq"])
        if "pre_run_checkpoint_id" not in revision_columns:
            batch_op.add_column(sa.Column("pre_run_checkpoint_id", sa.String(), nullable=True))
        if "ix_revisions_pre_run_checkpoint_id" not in revision_indexes:
            batch_op.create_index("ix_revisions_pre_run_checkpoint_id", ["pre_run_checkpoint_id"])
        if "graph_thread_id" not in revision_columns:
            batch_op.add_column(sa.Column("graph_thread_id", sa.String(), nullable=True))
        if "ix_revisions_graph_thread_id" not in revision_indexes:
            batch_op.create_index("ix_revisions_graph_thread_id", ["graph_thread_id"])

    if "agent_artifact" in tables:
        artifact_columns = _column_names(bind, "agent_artifact")
        artifact_indexes = _index_names(bind, "agent_artifact")
        with op.batch_alter_table("agent_artifact") as batch_op:
            if "revision_id" not in artifact_columns:
                batch_op.add_column(sa.Column("revision_id", sa.String(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_agent_artifact_revision_id_revisions",
                    "revisions",
                    ["revision_id"],
                    ["id"],
                )
            if "ix_agent_artifact_revision_id" not in artifact_indexes:
                batch_op.create_index("ix_agent_artifact_revision_id", ["revision_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "agent_artifact" in tables and "revision_id" in _column_names(bind, "agent_artifact"):
        indexes = _index_names(bind, "agent_artifact")
        with op.batch_alter_table("agent_artifact") as batch_op:
            if "ix_agent_artifact_revision_id" in indexes:
                batch_op.drop_index("ix_agent_artifact_revision_id")
            batch_op.drop_constraint("fk_agent_artifact_revision_id_revisions", type_="foreignkey")
            batch_op.drop_column("revision_id")

    revision_columns = _column_names(bind, "revisions")
    revision_indexes = _index_names(bind, "revisions")
    with op.batch_alter_table("revisions") as batch_op:
        if "ix_revisions_graph_thread_id" in revision_indexes:
            batch_op.drop_index("ix_revisions_graph_thread_id")
        if "graph_thread_id" in revision_columns:
            batch_op.drop_column("graph_thread_id")
        if "ix_revisions_pre_run_checkpoint_id" in revision_indexes:
            batch_op.drop_index("ix_revisions_pre_run_checkpoint_id")
        if "pre_run_checkpoint_id" in revision_columns:
            batch_op.drop_column("pre_run_checkpoint_id")
        if "ix_revisions_user_message_seq" in revision_indexes:
            batch_op.drop_index("ix_revisions_user_message_seq")
        if "user_message_seq" in revision_columns:
            batch_op.drop_column("user_message_seq")
        if "ix_revisions_user_message_id" in revision_indexes:
            batch_op.drop_index("ix_revisions_user_message_id")
        if "user_message_id" in revision_columns:
            batch_op.drop_column("user_message_id")

    if "agent_session_checkpoints" not in _table_names(bind):
        op.create_table(
            "agent_session_checkpoints",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("task_id", sa.String(), nullable=False),
            sa.Column("task_message_id", sa.String(), nullable=True),
            sa.Column("revision_id", sa.String(), nullable=True),
            sa.Column("checkpoint_id", sa.String(), nullable=False),
            sa.Column("checkpoint_ns", sa.String(), nullable=False, server_default=""),
            sa.Column("checkpoint_step", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("interrupt_id", sa.String(), nullable=True),
            sa.Column("interrupt_type", sa.String(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["task_message_id"], ["task_messages.id"]),
            sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "checkpoint_id", name="uq_agent_session_checkpoint"),
        )
        for column in (
            "session_id",
            "task_id",
            "task_message_id",
            "revision_id",
            "checkpoint_id",
            "interrupt_id",
            "interrupt_type",
            "status",
            "created_at",
        ):
            op.create_index(
                f"ix_agent_session_checkpoints_{column}",
                "agent_session_checkpoints",
                [column],
            )
