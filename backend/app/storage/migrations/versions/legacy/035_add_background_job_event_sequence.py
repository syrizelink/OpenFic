"""add background job event sequence counter

Revision ID: 035
Revises: 034
Create Date: 2026-05-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("background_jobs", "event_sequence"):
        op.add_column(
            "background_jobs",
            sa.Column("event_sequence", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    if _has_column("background_jobs", "event_sequence"):
        op.drop_column("background_jobs", "event_sequence")
