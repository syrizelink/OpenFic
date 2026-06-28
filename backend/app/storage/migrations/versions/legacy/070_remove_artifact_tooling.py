"""remove artifact tooling

Revision ID: 070
Revises: 069
Create Date: 2026-06-24 15:20:00.000000

"""

from __future__ import annotations

import json
from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "070"
down_revision = "069"
branch_labels = None
depends_on = None


def _table_names(bind: Any) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _decode_category_keys(raw_value: Any) -> list[str]:
    if isinstance(raw_value, list):
        return [item for item in raw_value if isinstance(item, str) and item]
    if isinstance(raw_value, str) and raw_value:
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, str) and item]
    return []


def _remove_artifact_category(bind: Any) -> None:
    if "agent_definitions" not in _table_names(bind):
        return

    rows = bind.execute(
        sa.text("SELECT id, tool_category_keys_json FROM agent_definitions")
    ).mappings()
    for row in rows:
        keys = _decode_category_keys(row["tool_category_keys_json"])
        cleaned = [item for item in keys if item != "artifact"]
        if cleaned == keys:
            continue
        bind.execute(
            sa.text(
                """
                UPDATE agent_definitions
                SET tool_category_keys_json = :tool_category_keys_json,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "tool_category_keys_json": json.dumps(cleaned, ensure_ascii=True),
            },
        )


def upgrade() -> None:
    bind = op.get_bind()
    _remove_artifact_category(bind)

    tables = _table_names(bind)
    if "agent_artifact" in tables:
        op.drop_table("agent_artifact")


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "agent_artifact" not in tables:
        op.create_table(
            "agent_artifact",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("task_id", sa.String(), nullable=False),
            sa.Column("project_id", sa.String(), nullable=False),
            sa.Column("chapter_id", sa.String(), nullable=True),
            sa.Column("revision_id", sa.String(), nullable=True),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("tool_name", sa.String(), nullable=True),
            sa.Column("tool_call_id", sa.String(), nullable=True),
            sa.Column("type", sa.String(length=100), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_artifact_session_id", "agent_artifact", ["session_id"])
        op.create_index("ix_agent_artifact_task_id", "agent_artifact", ["task_id"])
        op.create_index("ix_agent_artifact_project_id", "agent_artifact", ["project_id"])
        op.create_index("ix_agent_artifact_chapter_id", "agent_artifact", ["chapter_id"])
        op.create_index("ix_agent_artifact_revision_id", "agent_artifact", ["revision_id"])
        op.create_index("ix_agent_artifact_agent_id", "agent_artifact", ["agent_id"])
        op.create_index("ix_agent_artifact_tool_name", "agent_artifact", ["tool_name"])
        op.create_index("ix_agent_artifact_tool_call_id", "agent_artifact", ["tool_call_id"])
        op.create_index("ix_agent_artifact_type", "agent_artifact", ["type"])
        op.create_index("ix_agent_artifact_created_at", "agent_artifact", ["created_at"])
        op.create_index(
            "ix_agent_artifact_session_type_created_id",
            "agent_artifact",
            ["session_id", "type", "created_at", "id"],
        )
