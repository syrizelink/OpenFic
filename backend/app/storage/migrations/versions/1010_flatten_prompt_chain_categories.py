"""flatten prompt chain categories

Revision ID: 1010
Revises: 1009
Create Date: 2026-07-12 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlmodel import AutoString


revision: str = "1010"
down_revision: Union[str, Sequence[str], None] = "1009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _prompt_id(mode_name: str, task_name: str, agent_name: str | None) -> str:
    if mode_name == "background" and task_name == "session_title":
        return "session-title"
    if mode_name == "assistant" and task_name == "compaction":
        return "session-compaction"
    if mode_name == "memory" and task_name == "mid_range_summary":
        return "memory-chapter-summary"
    if mode_name == "memory" and task_name == "far_range_summary":
        return "memory-range-summary"
    if mode_name == "assistant" and task_name == "agent" and agent_name:
        builtins = {"primary", "explorer", "composer", "auditor", "writer", "actor", "reviewer"}
        prefix = "builtin-agent" if agent_name in builtins else "custom-agent"
        return f"{prefix}--{agent_name}"
    raise ValueError(f"无法迁移未知提示词链: {mode_name}/{task_name}/{agent_name or ''}")


def upgrade() -> None:
    """Upgrade schema and retain every existing prompt-chain version."""
    with op.batch_alter_table("prompt_chain_versions") as batch_op:
        batch_op.add_column(sa.Column("prompt_id", AutoString(length=300), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, mode_name, task_name, agent_name FROM prompt_chain_versions"
        )
    ).mappings()
    for row in rows:
        connection.execute(
            sa.text("UPDATE prompt_chain_versions SET prompt_id = :prompt_id WHERE id = :id"),
            {"id": row["id"], "prompt_id": _prompt_id(row["mode_name"], row["task_name"], row["agent_name"])},
        )

    with op.batch_alter_table("prompt_chain_versions") as batch_op:
        batch_op.alter_column("prompt_id", nullable=False)
        batch_op.drop_column("mode_name")
        batch_op.drop_column("task_name")
        batch_op.drop_column("agent_name")
        batch_op.create_index("ix_prompt_chain_versions_prompt_id", ["prompt_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema and restore legacy columns from prompt IDs."""
    with op.batch_alter_table("prompt_chain_versions") as batch_op:
        batch_op.drop_index("ix_prompt_chain_versions_prompt_id")
        batch_op.add_column(sa.Column("agent_name", AutoString(length=100), nullable=True))
        batch_op.add_column(sa.Column("task_name", AutoString(length=100), nullable=True))
        batch_op.add_column(sa.Column("mode_name", AutoString(length=100), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, prompt_id FROM prompt_chain_versions")).mappings()
    for row in rows:
        prompt_id = row["prompt_id"]
        if prompt_id == "session-title":
            values = {"mode_name": "background", "task_name": "session_title", "agent_name": None}
        elif prompt_id == "session-compaction":
            values = {"mode_name": "assistant", "task_name": "compaction", "agent_name": None}
        elif prompt_id == "memory-chapter-summary":
            values = {"mode_name": "memory", "task_name": "mid_range_summary", "agent_name": None}
        elif prompt_id == "memory-range-summary":
            values = {"mode_name": "memory", "task_name": "far_range_summary", "agent_name": None}
        elif prompt_id.startswith("builtin-agent--") or prompt_id.startswith("custom-agent--"):
            values = {
                "mode_name": "assistant",
                "task_name": "agent",
                "agent_name": prompt_id.split("--", maxsplit=1)[1],
            }
        else:
            raise ValueError(f"无法回滚未知提示词链: {prompt_id}")
        connection.execute(
            sa.text(
                "UPDATE prompt_chain_versions "
                "SET mode_name = :mode_name, task_name = :task_name, agent_name = :agent_name "
                "WHERE id = :id"
            ),
            {"id": row["id"], **values},
        )

    with op.batch_alter_table("prompt_chain_versions") as batch_op:
        batch_op.alter_column("mode_name", nullable=False)
        batch_op.alter_column("task_name", nullable=False)
        batch_op.drop_column("prompt_id")
