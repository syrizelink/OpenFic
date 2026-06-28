"""remove builtin agent definition rows

Revision ID: 055
Revises: 054
Create Date: 2026-06-08

"""

from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "055"
down_revision: Union[str, None] = "054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BUILTIN_AGENT_ROWS: tuple[dict[str, object], ...] = (
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
            "plan_read",
            "plan_write",
            "chapter_read",
        ],
        "skill_policy": "disabled",
        "metadata_json": {},
        "enabled": True,
        "order_index": 0,
    },
    {
        "id": "agent_definition_explorer",
        "key": "explorer",
        "display_name": "Explorer",
        "kind": "subagent",
        "prompt_agent_name": "explorer",
        "model_id": None,
        "tool_category_keys_json": [
            "plan_read",
            "chapter_read",
        ],
        "skill_policy": "enabled_by_agent",
        "metadata_json": {},
        "enabled": True,
        "order_index": 1,
    },
    {
        "id": "agent_definition_composer",
        "key": "composer",
        "display_name": "Composer",
        "kind": "subagent",
        "prompt_agent_name": "composer",
        "model_id": None,
        "tool_category_keys_json": [
            "artifact",
            "plan_read",
            "plan_write",
            "chapter_read",
        ],
        "skill_policy": "enabled_by_agent",
        "metadata_json": {},
        "enabled": True,
        "order_index": 2,
    },
    {
        "id": "agent_definition_writer",
        "key": "writer",
        "display_name": "Writer",
        "kind": "subagent",
        "prompt_agent_name": "writer",
        "model_id": None,
        "tool_category_keys_json": [
            "artifact",
            "plan_read",
            "chapter_read",
            "chapter_write",
        ],
        "skill_policy": "enabled_by_agent",
        "metadata_json": {},
        "enabled": True,
        "order_index": 3,
    },
    {
        "id": "agent_definition_reviewer",
        "key": "reviewer",
        "display_name": "Reviewer",
        "kind": "subagent",
        "prompt_agent_name": "reviewer",
        "model_id": None,
        "tool_category_keys_json": [
            "artifact",
            "plan_read",
            "chapter_read",
        ],
        "skill_policy": "enabled_by_agent",
        "metadata_json": {},
        "enabled": True,
        "order_index": 4,
    },
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DELETE FROM agent_definitions
            WHERE key IN ('primary', 'explorer', 'composer', 'writer', 'reviewer', 'clarifier')
            """
        )
    )


def downgrade() -> None:
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
                **row,
                "created_at": now,
                "updated_at": now,
            }
            for row in BUILTIN_AGENT_ROWS
        ],
    )
