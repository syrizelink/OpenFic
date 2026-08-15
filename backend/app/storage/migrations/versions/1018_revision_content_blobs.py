"""add revision content blobs

Revision ID: 1018
Revises: 1017
Create Date: 2026-08-15 16:30:00.000000
"""

from __future__ import annotations

import zlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision: str = "1018"
down_revision: Union[str, Sequence[str], None] = "1017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BACKFILL_MARKER_TABLE = "openfic_maintenance_migrations"
_BACKFILL_MARKER = "revision_content_blobs_backfill_v1"
_RESTORE_BATCH_SIZE = 500
_BLOB_BACKED_FIELDS = (
    ("commits", "snapshot_content", "snapshot_content_blob_id"),
    ("commits", "new_content", "new_content_blob_id"),
    ("revision_chapter_snapshots", "content", "content_blob_id"),
    ("revision_note_snapshots", "content", "content_blob_id"),
    ("revision_world_entry_snapshots", "content", "content_blob_id"),
    (
        "revision_character_snapshots",
        "description",
        "description_blob_id",
    ),
)


def upgrade() -> None:
    op.create_table(
        "revision_content_blobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("raw_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "commits",
        sa.Column("snapshot_content_blob_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "commits",
        sa.Column("new_content_blob_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "revision_chapter_snapshots",
        sa.Column("content_blob_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "revision_note_snapshots",
        sa.Column("content_blob_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "revision_world_entry_snapshots",
        sa.Column("content_blob_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "revision_character_snapshots",
        sa.Column("description_blob_id", sa.String(length=64), nullable=True),
    )


def _restore_blob_backed_content(bind: Connection) -> None:
    """Restore compressed text to the legacy inline columns before downgrade."""
    for table_name, content_column, blob_id_column in _BLOB_BACKED_FIELDS:
        last_id: str | None = None
        select_statement = sa.text(
            f"SELECT source.id AS row_id, blob.data AS blob_data "
            f"FROM {table_name} AS source "
            "LEFT JOIN revision_content_blobs AS blob "
            f"ON blob.id = source.{blob_id_column} "
            f"WHERE source.{blob_id_column} IS NOT NULL "
            "AND (:last_id IS NULL OR source.id > :last_id) "
            "ORDER BY source.id LIMIT :batch_size"
        )
        update_statement = sa.text(
            f"UPDATE {table_name} SET {content_column} = :content "
            "WHERE id = :row_id"
        )

        while True:
            rows = bind.execute(
                select_statement,
                {"last_id": last_id, "batch_size": _RESTORE_BATCH_SIZE},
            ).mappings().all()
            if not rows:
                break

            updates: list[dict[str, str]] = []
            for row in rows:
                blob_data = row["blob_data"]
                if blob_data is None:
                    raise RuntimeError(
                        f"Cannot downgrade: {table_name} row {row['row_id']} "
                        f"references a missing revision content blob"
                    )
                updates.append(
                    {
                        "row_id": str(row["row_id"]),
                        "content": zlib.decompress(bytes(blob_data)).decode("utf-8"),
                    }
                )

            bind.execute(update_statement, updates)
            last_id = str(rows[-1]["row_id"])


def _reset_backfill_marker(bind: Connection) -> None:
    """Allow a later re-upgrade to backfill the restored inline content again."""
    if _BACKFILL_MARKER_TABLE not in sa.inspect(bind).get_table_names():
        return
    bind.execute(
        sa.text(
            f"DELETE FROM {_BACKFILL_MARKER_TABLE} WHERE name = :name"
        ),
        {"name": _BACKFILL_MARKER},
    )


def downgrade() -> None:
    bind = op.get_bind()
    _restore_blob_backed_content(bind)
    _reset_backfill_marker(bind)
    op.drop_column("revision_character_snapshots", "description_blob_id")
    op.drop_column("revision_world_entry_snapshots", "content_blob_id")
    op.drop_column("revision_note_snapshots", "content_blob_id")
    op.drop_column("revision_chapter_snapshots", "content_blob_id")
    op.drop_column("commits", "new_content_blob_id")
    op.drop_column("commits", "snapshot_content_blob_id")
    op.drop_table("revision_content_blobs")
