"""repair the revisions task foreign key omitted by the initial migration

Revision ID: 1022
Revises: 1021
Create Date: 2026-09-01
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision: str = "1022"
down_revision: Union[str, Sequence[str], None] = "1021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = "fk_revisions_task_id_tasks_1022"


def _foreign_key_columns(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _is_task_foreign_key(foreign_key: Mapping[str, object]) -> bool:
    return (
        _foreign_key_columns(foreign_key.get("constrained_columns")) == ("task_id",)
        and foreign_key.get("referred_table") == "tasks"
        and _foreign_key_columns(foreign_key.get("referred_columns")) == ("id",)
    )


def _has_task_foreign_key(bind: Connection) -> bool:
    if op.get_context().as_sql:
        return False
    return any(
        _is_task_foreign_key(foreign_key)
        for foreign_key in sa.inspect(bind).get_foreign_keys("revisions")
    )


def _has_repair_foreign_key(bind: Connection) -> bool:
    if op.get_context().as_sql:
        return True
    return any(
        foreign_key.get("name") == CONSTRAINT_NAME
        and _is_task_foreign_key(foreign_key)
        for foreign_key in sa.inspect(bind).get_foreign_keys("revisions")
    )


def upgrade() -> None:
    """Add the missing task foreign key without duplicating an existing one."""
    bind = op.get_bind()
    if _has_task_foreign_key(bind):
        return

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("revisions", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                CONSTRAINT_NAME,
                "tasks",
                ["task_id"],
                ["id"],
            )
        return

    op.create_foreign_key(
        CONSTRAINT_NAME,
        "revisions",
        "tasks",
        ["task_id"],
        ["id"],
    )


def downgrade() -> None:
    """Remove only the repair constraint created by this revision."""
    bind = op.get_bind()
    if not _has_repair_foreign_key(bind):
        return

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("revisions", recreate="always") as batch_op:
            batch_op.drop_constraint(CONSTRAINT_NAME, type_="foreignkey")
        return

    op.drop_constraint(CONSTRAINT_NAME, "revisions", type_="foreignkey")
