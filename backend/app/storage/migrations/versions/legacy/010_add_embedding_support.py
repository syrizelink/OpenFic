"""Add embedding support to models

Revision ID: 010
Revises: 009
Create Date: 2026-01-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add task_type, dimensions, and encoding_format fields to models table."""
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if models table exists
    if "models" not in inspector.get_table_names():
        return

    existing_columns = [col["name"] for col in inspector.get_columns("models")]

    # Add task_type column if it doesn't exist
    if "task_type" not in existing_columns:
        op.add_column(
            "models",
            sa.Column(
                "task_type",
                sa.String(length=20),
                nullable=False,
                server_default="llm",
            ),
        )

    # Add dimensions column if it doesn't exist
    if "dimensions" not in existing_columns:
        op.add_column(
            "models",
            sa.Column("dimensions", sa.Integer(), nullable=True),
        )

    # Add encoding_format column if it doesn't exist
    if "encoding_format" not in existing_columns:
        op.add_column(
            "models",
            sa.Column("encoding_format", sa.String(length=20), nullable=True),
        )

    # Create index on task_type if it doesn't exist
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("models")]
    if "ix_models_task_type" not in existing_indexes:
        op.create_index(
            op.f("ix_models_task_type"), "models", ["task_type"], unique=False
        )


def downgrade() -> None:
    """Remove embedding support fields from models table."""
    op.drop_index(op.f("ix_models_task_type"), table_name="models")
    op.drop_column("models", "encoding_format")
    op.drop_column("models", "dimensions")
    op.drop_column("models", "task_type")
