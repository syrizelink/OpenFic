"""add task token usage

Revision ID: 027
Revises: 026
Create Date: 2026-05-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Add model context length and task token counters, clearing old task data."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    for table_name in ("task_messages", "agent_audit_logs", "tasks"):
        if table_name in table_names:
            op.execute(sa.text(f"DELETE FROM {table_name}"))

    model_columns = _existing_columns("models")
    if "context_length" not in model_columns:
        op.add_column(
            "models",
            sa.Column("context_length", sa.Integer(), nullable=False, server_default="128000"),
        )

    task_columns = _existing_columns("tasks")
    for column_name in (
        "token_input",
        "token_output",
        "token_cache",
        "context_input_tokens",
    ):
        if column_name not in task_columns:
            op.add_column(
                "tasks",
                sa.Column(column_name, sa.Integer(), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    """Remove task token counters and model context length."""
    task_columns = _existing_columns("tasks")
    for column_name in (
        "context_input_tokens",
        "token_cache",
        "token_output",
        "token_input",
    ):
        if column_name in task_columns:
            op.drop_column("tasks", column_name)

    if "context_length" in _existing_columns("models"):
        op.drop_column("models", "context_length")
