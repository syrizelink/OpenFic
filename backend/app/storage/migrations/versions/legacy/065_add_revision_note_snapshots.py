"""add revision_note_snapshots and revision_note_category_snapshots tables

Revision ID: 065
Revises: 064
Create Date: 2026-06-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "065"
down_revision: Union[str, None] = "064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "revision_note_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("revision_id", sa.String(), nullable=False),
        sa.Column("note_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("exists", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("category_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("is_locked", sa.Boolean(), nullable=True),
        sa.Column("is_hidden", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
        sa.UniqueConstraint(
            "revision_id", "note_id", name="uq_revision_note_snapshot"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_revision_note_snapshots_revision_id",
        "revision_note_snapshots",
        ["revision_id"],
    )
    op.create_index(
        "ix_revision_note_snapshots_note_id",
        "revision_note_snapshots",
        ["note_id"],
    )
    op.create_index(
        "ix_revision_note_snapshots_project_id",
        "revision_note_snapshots",
        ["project_id"],
    )
    op.create_index(
        "ix_revision_note_snapshots_category_id",
        "revision_note_snapshots",
        ["category_id"],
    )
    op.create_index(
        "ix_revision_note_snapshots_created_at",
        "revision_note_snapshots",
        ["created_at"],
    )

    op.create_table(
        "revision_note_category_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("revision_id", sa.String(), nullable=False),
        sa.Column("category_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("exists", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
        sa.UniqueConstraint(
            "revision_id",
            "category_id",
            name="uq_revision_note_category_snapshot",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_revision_note_category_snapshots_revision_id",
        "revision_note_category_snapshots",
        ["revision_id"],
    )
    op.create_index(
        "ix_revision_note_category_snapshots_category_id",
        "revision_note_category_snapshots",
        ["category_id"],
    )
    op.create_index(
        "ix_revision_note_category_snapshots_project_id",
        "revision_note_category_snapshots",
        ["project_id"],
    )
    op.create_index(
        "ix_revision_note_category_snapshots_parent_id",
        "revision_note_category_snapshots",
        ["parent_id"],
    )
    op.create_index(
        "ix_revision_note_category_snapshots_created_at",
        "revision_note_category_snapshots",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_revision_note_category_snapshots_created_at",
        table_name="revision_note_category_snapshots",
    )
    op.drop_index(
        "ix_revision_note_category_snapshots_parent_id",
        table_name="revision_note_category_snapshots",
    )
    op.drop_index(
        "ix_revision_note_category_snapshots_project_id",
        table_name="revision_note_category_snapshots",
    )
    op.drop_index(
        "ix_revision_note_category_snapshots_category_id",
        table_name="revision_note_category_snapshots",
    )
    op.drop_index(
        "ix_revision_note_category_snapshots_revision_id",
        table_name="revision_note_category_snapshots",
    )
    op.drop_table("revision_note_category_snapshots")

    op.drop_index(
        "ix_revision_note_snapshots_created_at", table_name="revision_note_snapshots"
    )
    op.drop_index(
        "ix_revision_note_snapshots_category_id", table_name="revision_note_snapshots"
    )
    op.drop_index(
        "ix_revision_note_snapshots_project_id", table_name="revision_note_snapshots"
    )
    op.drop_index(
        "ix_revision_note_snapshots_note_id", table_name="revision_note_snapshots"
    )
    op.drop_index(
        "ix_revision_note_snapshots_revision_id", table_name="revision_note_snapshots"
    )
    op.drop_table("revision_note_snapshots")
