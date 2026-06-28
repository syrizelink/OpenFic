"""add notes and note_categories tables

Revision ID: 063
Revises: 062
Create Date: 2026-06-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "063"
down_revision: Union[str, None] = "062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "note_categories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["note_categories.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_note_categories_parent_id",
        "note_categories",
        ["parent_id"],
    )
    op.create_index(
        "ix_note_categories_project_id",
        "note_categories",
        ["project_id"],
    )

    op.create_table(
        "notes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("category_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["note_categories.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notes_category_id", "notes", ["category_id"])
    op.create_index("ix_notes_project_id", "notes", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_notes_project_id", table_name="notes")
    op.drop_index("ix_notes_category_id", table_name="notes")
    op.drop_table("notes")
    op.drop_index("ix_note_categories_project_id", table_name="note_categories")
    op.drop_index("ix_note_categories_parent_id", table_name="note_categories")
    op.drop_table("note_categories")
