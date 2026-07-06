"""add revision character snapshots

Revision ID: 1006
Revises: 1005
Create Date: 2026-07-06 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlmodel import AutoString


# revision identifiers, used by Alembic.
revision: str = "1006"
down_revision: Union[str, Sequence[str], None] = "1005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "revision_character_snapshots",
        sa.Column("id", AutoString(), nullable=False),
        sa.Column("revision_id", AutoString(), nullable=False),
        sa.Column("character_id", AutoString(), nullable=False),
        sa.Column("project_id", AutoString(), nullable=False),
        sa.Column("exists", sa.Boolean(), nullable=False),
        sa.Column("name", AutoString(length=200), nullable=True),
        sa.Column("description", AutoString(), nullable=True),
        sa.Column("is_favorited", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id", "character_id", name="uq_revision_character_snapshot"),
    )
    op.create_index(op.f("ix_revision_character_snapshots_character_id"), "revision_character_snapshots", ["character_id"], unique=False)
    op.create_index(op.f("ix_revision_character_snapshots_created_at"), "revision_character_snapshots", ["created_at"], unique=False)
    op.create_index(op.f("ix_revision_character_snapshots_project_id"), "revision_character_snapshots", ["project_id"], unique=False)
    op.create_index(op.f("ix_revision_character_snapshots_revision_id"), "revision_character_snapshots", ["revision_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_revision_character_snapshots_revision_id"), table_name="revision_character_snapshots")
    op.drop_index(op.f("ix_revision_character_snapshots_project_id"), table_name="revision_character_snapshots")
    op.drop_index(op.f("ix_revision_character_snapshots_created_at"), table_name="revision_character_snapshots")
    op.drop_index(op.f("ix_revision_character_snapshots_character_id"), table_name="revision_character_snapshots")
    op.drop_table("revision_character_snapshots")
