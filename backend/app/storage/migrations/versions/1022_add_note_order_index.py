"""add persistent mixed ordering for notes

Revision ID: 1022
Revises: 1021
Create Date: 2026-09-05
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision: str = "1022"
down_revision: Union[str, Sequence[str], None] = "1021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_mixed_order(connection: Connection) -> None:
    categories = (
        connection.execute(
            sa.text(
                "SELECT id, project_id, parent_id FROM note_categories "
                "ORDER BY project_id, parent_id, title, id"
            )
        )
        .mappings()
        .all()
    )
    notes = (
        connection.execute(
            sa.text(
                "SELECT id, project_id, category_id FROM notes "
                "ORDER BY project_id, category_id, title, id"
            )
        )
        .mappings()
        .all()
    )
    groups: dict[tuple[str, str | None], list[tuple[str, str]]] = {}
    for row in categories:
        groups.setdefault((row["project_id"], row["parent_id"]), []).append(
            ("note_categories", row["id"])
        )
    for row in notes:
        groups.setdefault((row["project_id"], row["category_id"]), []).append(
            ("notes", row["id"])
        )
    for siblings in groups.values():
        for index, (table, item_id) in enumerate(siblings):
            connection.execute(
                sa.text(f"UPDATE {table} SET order_index = :index WHERE id = :item_id"),
                {"index": index, "item_id": item_id},
            )


def upgrade() -> None:
    op.add_column(
        "note_categories",
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "notes",
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    _backfill_mixed_order(op.get_bind())
    with op.batch_alter_table("note_categories") as batch:
        batch.alter_column("order_index", server_default=None)
    with op.batch_alter_table("notes") as batch:
        batch.alter_column("order_index", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("notes") as batch:
        batch.drop_column("order_index")
    with op.batch_alter_table("note_categories") as batch:
        batch.drop_column("order_index")
