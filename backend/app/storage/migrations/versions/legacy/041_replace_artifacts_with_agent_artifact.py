"""replace artifacts with agent_artifact

Revision ID: 041
Revises: 040
Create Date: 2026-05-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "artifacts" in tables:
        op.drop_table("artifacts")

    tables = _table_names(bind)
    if "agent_artifact" not in tables:
        op.create_table(
            "agent_artifact",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("task_id", sa.String(), nullable=False),
            sa.Column("project_id", sa.String(), nullable=False),
            sa.Column("chapter_id", sa.String(), nullable=True),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("tool_name", sa.String(), nullable=True),
            sa.Column("tool_call_id", sa.String(), nullable=True),
            sa.Column("type", sa.String(length=100), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = _index_names(bind, "agent_artifact")
    if "ix_agent_artifact_session_id" not in existing_indexes:
        op.create_index("ix_agent_artifact_session_id", "agent_artifact", ["session_id"])
    if "ix_agent_artifact_task_id" not in existing_indexes:
        op.create_index("ix_agent_artifact_task_id", "agent_artifact", ["task_id"])
    if "ix_agent_artifact_project_id" not in existing_indexes:
        op.create_index("ix_agent_artifact_project_id", "agent_artifact", ["project_id"])
    if "ix_agent_artifact_chapter_id" not in existing_indexes:
        op.create_index("ix_agent_artifact_chapter_id", "agent_artifact", ["chapter_id"])
    if "ix_agent_artifact_agent_id" not in existing_indexes:
        op.create_index("ix_agent_artifact_agent_id", "agent_artifact", ["agent_id"])
    if "ix_agent_artifact_tool_name" not in existing_indexes:
        op.create_index("ix_agent_artifact_tool_name", "agent_artifact", ["tool_name"])
    if "ix_agent_artifact_tool_call_id" not in existing_indexes:
        op.create_index("ix_agent_artifact_tool_call_id", "agent_artifact", ["tool_call_id"])
    if "ix_agent_artifact_type" not in existing_indexes:
        op.create_index("ix_agent_artifact_type", "agent_artifact", ["type"])
    if "ix_agent_artifact_created_at" not in existing_indexes:
        op.create_index("ix_agent_artifact_created_at", "agent_artifact", ["created_at"])
    if "ix_agent_artifact_session_type_created_id" not in existing_indexes:
        op.create_index(
            "ix_agent_artifact_session_type_created_id",
            "agent_artifact",
            ["session_id", "type", "created_at", "id"],
        )

    bind.execute(sa.text("UPDATE tasks SET mode = 'plan' WHERE mode != 'plan'"))


def downgrade() -> None:
    op.drop_index(
        "ix_agent_artifact_session_type_created_id", table_name="agent_artifact"
    )
    op.drop_index("ix_agent_artifact_created_at", table_name="agent_artifact")
    op.drop_index("ix_agent_artifact_type", table_name="agent_artifact")
    op.drop_index("ix_agent_artifact_tool_call_id", table_name="agent_artifact")
    op.drop_index("ix_agent_artifact_tool_name", table_name="agent_artifact")
    op.drop_index("ix_agent_artifact_agent_id", table_name="agent_artifact")
    op.drop_index("ix_agent_artifact_chapter_id", table_name="agent_artifact")
    op.drop_index("ix_agent_artifact_project_id", table_name="agent_artifact")
    op.drop_index("ix_agent_artifact_task_id", table_name="agent_artifact")
    op.drop_index("ix_agent_artifact_session_id", table_name="agent_artifact")
    op.drop_table("agent_artifact")
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("agent_session_id", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=True),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifacts_project_id", "artifacts", ["project_id"])
    op.create_index("ix_artifacts_agent_session_id", "artifacts", ["agent_session_id"])
    op.create_index("ix_artifacts_chapter_id", "artifacts", ["chapter_id"])
    op.create_index("ix_artifacts_type", "artifacts", ["type"])
