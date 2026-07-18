"""consolidate session plans

Revision ID: 1014
Revises: 1013
Create Date: 2026-07-18 13:20:00.000000
"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1014"
down_revision: Union[str, Sequence[str], None] = "1013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _keep_latest_plan_per_session()

    with op.batch_alter_table("plans") as batch_op:
        batch_op.drop_index("ix_plans_scope_id")
        batch_op.drop_index("ix_plans_status")
        batch_op.alter_column("scope_id", new_column_name="session_id", existing_type=sa.String(64))
        batch_op.drop_column("topic")
        batch_op.drop_column("description")
        batch_op.drop_column("status")
    op.create_index("uq_plans_session_id", "plans", ["session_id"], unique=True)

    with op.batch_alter_table("plan_todos") as batch_op:
        batch_op.drop_column("title")
        batch_op.add_column(
            sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium")
        )

    _replace_legacy_plan_categories()
    _replace_legacy_plan_permissions()


def _keep_latest_plan_per_session() -> None:
    bind = op.get_bind()
    duplicate_plan_rows = bind.execute(
        sa.text(
            """
            SELECT older.id
            FROM plans AS older
            JOIN plans AS newer
              ON newer.scope_id = older.scope_id
             AND (
                newer.created_at > older.created_at
                OR (newer.created_at = older.created_at AND newer.id > older.id)
             )
            """
        )
    ).fetchall()
    duplicate_plan_ids = [row.id for row in duplicate_plan_rows]
    if not duplicate_plan_ids:
        return
    bind.execute(
        sa.delete(sa.table("plan_todos")).where(
            sa.column("plan_id").in_(duplicate_plan_ids)
        )
    )
    bind.execute(
        sa.delete(sa.table("plans")).where(sa.column("id").in_(duplicate_plan_ids))
    )


def _replace_legacy_plan_categories() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, enabled_tool_categories FROM agent_definitions")).fetchall()
    for row in rows:
        raw_categories = row.enabled_tool_categories
        if isinstance(raw_categories, str):
            try:
                categories = json.loads(raw_categories)
            except json.JSONDecodeError:
                continue
        else:
            categories = raw_categories
        if not isinstance(categories, list):
            continue
        normalized = [
            "plan" if category in {"plan_read", "plan_write"} else category
            for category in categories
        ]
        deduplicated = list(dict.fromkeys(normalized))
        if deduplicated == categories:
            continue
        statement = sa.text(
            "UPDATE agent_definitions SET enabled_tool_categories = :categories WHERE id = :id"
        ).bindparams(sa.bindparam("categories", type_=sa.JSON()))
        bind.execute(
            statement,
            {"id": row.id, "categories": deduplicated},
        )


def _replace_legacy_plan_permissions() -> None:
    bind = op.get_bind()
    row = bind.execute(
        sa.text("SELECT id, value FROM settings WHERE key = 'agent_tool_permissions'")
    ).fetchone()
    if row is None or not isinstance(row.value, str):
        return
    try:
        permissions = json.loads(row.value)
    except json.JSONDecodeError:
        return
    if not isinstance(permissions, list):
        return
    write_plan_mode = "ask"
    normalized: list[object] = []
    for permission in permissions:
        if not isinstance(permission, dict):
            normalized.append(permission)
            continue
        tool_name = permission.get("tool_name")
        mode = permission.get("mode")
        if tool_name in {"create_plan", "update_plan", "write_plan"} and mode in {
            "allow",
            "ask",
            "deny",
        }:
            write_plan_mode = mode
        if tool_name in {"create_plan", "update_plan", "get_plan", "list_plan", "write_plan"}:
            continue
        normalized.append(permission)
    normalized.append({"tool_name": "write_plan", "mode": write_plan_mode})
    bind.execute(
        sa.text("UPDATE settings SET value = :value WHERE id = :id"),
        {"id": row.id, "value": json.dumps(normalized, ensure_ascii=False)},
    )


def downgrade() -> None:
    op.drop_index("uq_plans_session_id", table_name="plans")

    with op.batch_alter_table("plan_todos") as batch_op:
        batch_op.drop_column("priority")
        batch_op.add_column(sa.Column("title", sa.Text(), nullable=False, server_default=""))

    with op.batch_alter_table("plans") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"))
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("topic", sa.String(length=200), nullable=False, server_default=""))
        batch_op.alter_column("session_id", new_column_name="scope_id", existing_type=sa.String(64))
    op.create_index("ix_plans_scope_id", "plans", ["scope_id"])
    op.create_index("ix_plans_status", "plans", ["status"])
