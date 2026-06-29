"""remove plan dependency field and enable composer note write

Revision ID: 1002
Revises: 1001
Create Date: 2026-06-29 00:00:00.000000

"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1002"
down_revision: Union[str, Sequence[str], None] = "1001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _load_tool_category_keys(raw_value: object) -> list[str]:
    if isinstance(raw_value, list):
        return [str(item) for item in raw_value]
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []


def _upgrade_composer_tool_categories() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, tool_category_keys_json FROM agent_definitions WHERE key = 'composer'"
        )
    ).fetchall()
    for row in rows:
        tool_category_keys = _load_tool_category_keys(row.tool_category_keys_json)
        if "note_write" in tool_category_keys:
            continue
        tool_category_keys.append("note_write")
        bind.execute(
            sa.text(
                "UPDATE agent_definitions SET tool_category_keys_json = :tool_category_keys_json WHERE id = :id"
            ),
            {
                "id": row.id,
                "tool_category_keys_json": json.dumps(tool_category_keys, ensure_ascii=False),
            },
        )


def _downgrade_composer_tool_categories() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, tool_category_keys_json FROM agent_definitions WHERE key = 'composer'"
        )
    ).fetchall()
    for row in rows:
        tool_category_keys = [
            key for key in _load_tool_category_keys(row.tool_category_keys_json) if key != "note_write"
        ]
        bind.execute(
            sa.text(
                "UPDATE agent_definitions SET tool_category_keys_json = :tool_category_keys_json WHERE id = :id"
            ),
            {
                "id": row.id,
                "tool_category_keys_json": json.dumps(tool_category_keys, ensure_ascii=False),
            },
        )


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.drop_column("parent_dependency_id")

    _upgrade_composer_tool_categories()


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_dependency_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_plans_parent_dependency_id_plan_todos",
            "plan_todos",
            ["parent_dependency_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_plans_parent_dependency_id",
            ["parent_dependency_id"],
        )

    _downgrade_composer_tool_categories()
