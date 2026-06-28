"""add revision status field

Revision ID: 019
Revises: 018
Create Date: 2026-04-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add status column to revisions table."""

    op.add_column(
        "revisions",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )

    op.create_index(
        op.f("ix_revisions_status"),
        "revisions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Remove status column from revisions table."""

    op.drop_index(op.f("ix_revisions_status"), table_name="revisions")
    op.drop_column("revisions", "status")
