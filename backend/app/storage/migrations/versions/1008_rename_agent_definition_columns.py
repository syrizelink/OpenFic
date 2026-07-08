"""rename agent definition columns and switch skills to id-based

Revision ID: 1008
Revises: 1007
Create Date: 2026-07-08 00:00:00.000000

"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1008"
down_revision: Union[str, Sequence[str], None] = "1007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _load_str_list(raw_value: object) -> list[str]:
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


def _migrate_skill_names_to_ids() -> None:
    """将 agent_definitions.enabled_skill_names_json 中的技能名称映射为技能 ID。"""
    bind = op.get_bind()

    name_to_id: dict[str, str] = {}
    skill_rows = bind.execute(sa.text("SELECT id, name FROM skills")).fetchall()
    for row in skill_rows:
        if row.name:
            name_to_id[row.name] = row.id

    agent_rows = bind.execute(
        sa.text("SELECT id, enabled_skill_names_json FROM agent_definitions")
    ).fetchall()
    for row in agent_rows:
        skill_names = _load_str_list(row.enabled_skill_names_json)
        skill_ids = [
            name_to_id[name] for name in skill_names if name and name in name_to_id
        ]
        bind.execute(
            sa.text(
                "UPDATE agent_definitions SET enabled_skills = :enabled_skills WHERE id = :id"
            ),
            {
                "id": row.id,
                "enabled_skills": json.dumps(skill_ids, ensure_ascii=False),
            },
        )


def _migrate_skill_ids_to_names() -> None:
    """将 agent_definitions.enabled_skills 中的技能 ID 映射回技能名称。"""
    bind = op.get_bind()

    id_to_name: dict[str, str] = {}
    skill_rows = bind.execute(sa.text("SELECT id, name FROM skills")).fetchall()
    for row in skill_rows:
        if row.id:
            id_to_name[row.id] = row.name

    agent_rows = bind.execute(
        sa.text("SELECT id, enabled_skills FROM agent_definitions")
    ).fetchall()
    for row in agent_rows:
        skill_ids = _load_str_list(row.enabled_skills)
        skill_names = [
            id_to_name[skill_id] for skill_id in skill_ids if skill_id and skill_id in id_to_name
        ]
        bind.execute(
            sa.text(
                "UPDATE agent_definitions SET enabled_skill_names_json = :enabled_skill_names_json WHERE id = :id"
            ),
            {
                "id": row.id,
                "enabled_skill_names_json": json.dumps(skill_names, ensure_ascii=False),
            },
        )


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.alter_column(
            "tool_category_keys_json",
            new_column_name="enabled_tool_categories",
            existing_type=sa.JSON(),
            nullable=False,
        )
        batch_op.add_column(sa.Column("enabled_skills", sa.JSON(), nullable=False, server_default="[]"))

    _migrate_skill_names_to_ids()

    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.drop_column("enabled_skill_names_json")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.add_column(
            sa.Column("enabled_skill_names_json", sa.JSON(), nullable=False, server_default="[]")
        )

    _migrate_skill_ids_to_names()

    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.drop_column("enabled_skills")
        batch_op.alter_column(
            "enabled_tool_categories",
            new_column_name="tool_category_keys_json",
            existing_type=sa.JSON(),
            nullable=False,
        )
