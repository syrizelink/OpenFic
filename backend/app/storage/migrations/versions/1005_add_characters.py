"""add characters

Revision ID: 1005
Revises: 1004
Create Date: 2026-07-05 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1005"
down_revision: Union[str, Sequence[str], None] = "1004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "characters",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("image_path", sa.String(), nullable=True),
        sa.Column("is_favorited", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_characters_project_id"), "characters", ["project_id"], unique=False)
    op.create_index(op.f("ix_characters_is_favorited"), "characters", ["is_favorited"], unique=False)
    op.create_index(op.f("ix_characters_updated_at"), "characters", ["updated_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_characters_updated_at"), table_name="characters")
    op.drop_index(op.f("ix_characters_is_favorited"), table_name="characters")
    op.drop_index(op.f("ix_characters_project_id"), table_name="characters")
    op.drop_table("characters")
