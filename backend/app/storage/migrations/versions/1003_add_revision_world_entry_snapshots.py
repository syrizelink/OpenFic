"""add revision world entry snapshots

Revision ID: 1003
Revises: 1002
Create Date: 2026-07-03 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlmodel import AutoString


# revision identifiers, used by Alembic.
revision: str = "1003"
down_revision: Union[str, Sequence[str], None] = "1002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "revision_world_entry_snapshots",
        sa.Column("id", AutoString(), nullable=False),
        sa.Column("revision_id", AutoString(), nullable=False),
        sa.Column("entry_id", AutoString(), nullable=False),
        sa.Column("project_id", AutoString(), nullable=False),
        sa.Column("exists", sa.Boolean(), nullable=False),
        sa.Column("world_info_id", AutoString(), nullable=True),
        sa.Column("uid", sa.Integer(), nullable=True),
        sa.Column("name", AutoString(length=200), nullable=True),
        sa.Column("entry_order", sa.Integer(), nullable=True),
        sa.Column("content", AutoString(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id", "entry_id", name="uq_revision_world_entry_snapshot"),
    )
    op.create_index(op.f("ix_revision_world_entry_snapshots_created_at"), "revision_world_entry_snapshots", ["created_at"], unique=False)
    op.create_index(op.f("ix_revision_world_entry_snapshots_entry_id"), "revision_world_entry_snapshots", ["entry_id"], unique=False)
    op.create_index(op.f("ix_revision_world_entry_snapshots_entry_order"), "revision_world_entry_snapshots", ["entry_order"], unique=False)
    op.create_index(op.f("ix_revision_world_entry_snapshots_project_id"), "revision_world_entry_snapshots", ["project_id"], unique=False)
    op.create_index(op.f("ix_revision_world_entry_snapshots_revision_id"), "revision_world_entry_snapshots", ["revision_id"], unique=False)
    op.create_index(op.f("ix_revision_world_entry_snapshots_uid"), "revision_world_entry_snapshots", ["uid"], unique=False)
    op.create_index(op.f("ix_revision_world_entry_snapshots_world_info_id"), "revision_world_entry_snapshots", ["world_info_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_revision_world_entry_snapshots_world_info_id"), table_name="revision_world_entry_snapshots")
    op.drop_index(op.f("ix_revision_world_entry_snapshots_uid"), table_name="revision_world_entry_snapshots")
    op.drop_index(op.f("ix_revision_world_entry_snapshots_revision_id"), table_name="revision_world_entry_snapshots")
    op.drop_index(op.f("ix_revision_world_entry_snapshots_project_id"), table_name="revision_world_entry_snapshots")
    op.drop_index(op.f("ix_revision_world_entry_snapshots_entry_order"), table_name="revision_world_entry_snapshots")
    op.drop_index(op.f("ix_revision_world_entry_snapshots_entry_id"), table_name="revision_world_entry_snapshots")
    op.drop_index(op.f("ix_revision_world_entry_snapshots_created_at"), table_name="revision_world_entry_snapshots")
    op.drop_table("revision_world_entry_snapshots")
