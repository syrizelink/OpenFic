"""add structured agent message fields

Revision ID: 025
Revises: 024
Create Date: 2026-05-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    ("message_type", sa.Column("message_type", sa.Text(), nullable=True)),
    ("message_status", sa.Column("message_status", sa.Text(), nullable=True)),
    ("display_channel", sa.Column("display_channel", sa.Text(), nullable=True)),
    ("payload", sa.Column("payload", sa.Text(), nullable=True)),
    ("correlation_id", sa.Column("correlation_id", sa.Text(), nullable=True)),
)

INDEXES: tuple[tuple[str, list[str]], ...] = (
    ("ix_task_messages_message_type", ["message_type"]),
    ("ix_task_messages_message_status", ["message_status"]),
    ("ix_task_messages_display_channel", ["display_channel"]),
    ("ix_task_messages_correlation_id", ["correlation_id"]),
)


def _existing_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "task_messages" not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns("task_messages")}


def _existing_indexes() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "task_messages" not in inspector.get_table_names():
        return set()
    return {
        name
        for index in inspector.get_indexes("task_messages")
        if isinstance(name := index["name"], str)
    }


def upgrade() -> None:
    existing_columns = _existing_columns()
    for name, column in COLUMNS:
        if name not in existing_columns:
            op.add_column("task_messages", column)

    existing_indexes = _existing_indexes()
    for name, columns in INDEXES:
        if name not in existing_indexes:
            op.create_index(name, "task_messages", columns, unique=False)


def downgrade() -> None:
    existing_indexes = _existing_indexes()
    for name, _columns in reversed(INDEXES):
        if name in existing_indexes:
            op.drop_index(name, table_name="task_messages")

    existing_columns = _existing_columns()
    for name, _column in reversed(COLUMNS):
        if name in existing_columns:
            op.drop_column("task_messages", name)
