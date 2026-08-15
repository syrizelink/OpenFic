"""add revision content blobs

Revision ID: 1018
Revises: 1017
Create Date: 2026-08-15 16:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1018"
down_revision: Union[str, Sequence[str], None] = "1017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


def downgrade() -> None:
    op.drop_column("revision_character_snapshots", "description_blob_id")
    op.drop_column("revision_world_entry_snapshots", "content_blob_id")
    op.drop_column("revision_note_snapshots", "content_blob_id")
    op.drop_column("revision_chapter_snapshots", "content_blob_id")
    op.drop_column("commits", "new_content_blob_id")
    op.drop_column("commits", "snapshot_content_blob_id")
    op.drop_table("revision_content_blobs")
