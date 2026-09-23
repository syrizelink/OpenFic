"""restore the deferred revision-to-task foreign key on PostgreSQL

Revision ID: 1024
Revises: 1023
Create Date: 2026-08-26 19:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect


revision: str = "1024"
down_revision: str | Sequence[str] | None = "1023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_NAME = "fk_revisions_task_id_tasks"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    existing_names = {
        foreign_key["name"]
        for foreign_key in inspect(bind).get_foreign_keys("revisions")
    }
    if _CONSTRAINT_NAME not in existing_names:
        op.create_foreign_key(
            _CONSTRAINT_NAME,
            "revisions",
            "tasks",
            ["task_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint(_CONSTRAINT_NAME, "revisions", type_="foreignkey")
