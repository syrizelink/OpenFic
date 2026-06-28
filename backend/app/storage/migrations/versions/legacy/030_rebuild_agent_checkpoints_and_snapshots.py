"""rebuild agent checkpoints and revision snapshots

Revision ID: 030
Revises: 029
Create Date: 2026-05-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    revision_columns = {column["name"] for column in inspector.get_columns("revisions")}

    bind.execute(sa.text("DELETE FROM agent_audit_logs"))
    bind.execute(
        sa.text(
            "DELETE FROM task_messages WHERE task_id IN "
            "(SELECT id FROM tasks WHERE mode = 'agent')"
        )
    )
    bind.execute(sa.text("DELETE FROM tasks WHERE mode = 'agent'"))
    bind.execute(sa.text("DELETE FROM commits"))
    bind.execute(sa.text("DELETE FROM revisions"))

    with op.batch_alter_table("revisions") as batch_op:
        if "revision_type" not in revision_columns:
            batch_op.add_column(
                sa.Column("revision_type", sa.String(length=30), nullable=False, server_default="manual")
            )
            batch_op.create_index("ix_revisions_revision_type", ["revision_type"])
        if "parent_revision_id" not in revision_columns:
            batch_op.add_column(sa.Column("parent_revision_id", sa.String(), nullable=True))
            batch_op.create_index("ix_revisions_parent_revision_id", ["parent_revision_id"])
            batch_op.create_foreign_key(
                "fk_revisions_parent_revision_id_revisions",
                "revisions",
                ["parent_revision_id"],
                ["id"],
            )
        if "task_id" not in revision_columns:
            batch_op.add_column(sa.Column("task_id", sa.String(), nullable=True))
            batch_op.create_index("ix_revisions_task_id", ["task_id"])
            batch_op.create_foreign_key(
                "fk_revisions_task_id_tasks",
                "tasks",
                ["task_id"],
                ["id"],
                use_alter=True,
            )
        if "started_at" not in revision_columns:
            batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
            batch_op.create_index("ix_revisions_started_at", ["started_at"])
        if "finished_at" not in revision_columns:
            batch_op.add_column(sa.Column("finished_at", sa.DateTime(), nullable=True))
            batch_op.create_index("ix_revisions_finished_at", ["finished_at"])
        if "updated_at" not in revision_columns:
            batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    bind.execute(sa.text("UPDATE revisions SET updated_at = created_at WHERE updated_at IS NULL"))

    if "revision_chapter_snapshots" in existing_tables:
        op.drop_table("revision_chapter_snapshots")
    if "agent_session_checkpoints" in existing_tables:
        op.drop_table("agent_session_checkpoints")

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
        op.create_index(f"ix_agent_session_checkpoints_{column}", "agent_session_checkpoints", [column])

    op.create_table(
        "revision_chapter_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("revision_id", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("exists", sa.Boolean(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("chapter_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id", "chapter_id", name="uq_revision_chapter_snapshot"),
    )
    for column in ("revision_id", "chapter_id", "project_id", "created_at"):
        op.create_index(f"ix_revision_chapter_snapshots_{column}", "revision_chapter_snapshots", [column])


def downgrade() -> None:
    for column in ("created_at", "project_id", "chapter_id", "revision_id"):
        op.drop_index(f"ix_revision_chapter_snapshots_{column}", table_name="revision_chapter_snapshots")
    op.drop_table("revision_chapter_snapshots")

    for column in (
        "created_at",
        "status",
        "interrupt_type",
        "interrupt_id",
        "checkpoint_id",
        "revision_id",
        "task_message_id",
        "task_id",
        "session_id",
    ):
        op.drop_index(f"ix_agent_session_checkpoints_{column}", table_name="agent_session_checkpoints")
    op.drop_table("agent_session_checkpoints")

    with op.batch_alter_table("revisions") as batch_op:
        batch_op.drop_constraint("fk_revisions_task_id_tasks", type_="foreignkey")
        batch_op.drop_constraint("fk_revisions_parent_revision_id_revisions", type_="foreignkey")
        batch_op.drop_index("ix_revisions_finished_at")
        batch_op.drop_index("ix_revisions_started_at")
        batch_op.drop_index("ix_revisions_task_id")
        batch_op.drop_index("ix_revisions_parent_revision_id")
        batch_op.drop_index("ix_revisions_revision_type")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("finished_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("task_id")
        batch_op.drop_column("parent_revision_id")
        batch_op.drop_column("revision_type")
