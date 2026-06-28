"""Add DeepSeek model parameters

Revision ID: 022
Revises: 021
Create Date: 2026-04-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add DeepSeek-only model parameter fields."""
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    if "models" not in inspector.get_table_names():
        return

    existing_columns = [col["name"] for col in inspector.get_columns("models")]

    if "deepseek_reasoning_effort" not in existing_columns:
        op.add_column(
            "models",
            sa.Column("deepseek_reasoning_effort", sa.String(length=20), nullable=True),
        )

    if "deepseek_thinking_type" not in existing_columns:
        op.add_column(
            "models",
            sa.Column("deepseek_thinking_type", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    """Remove DeepSeek-only model parameter fields."""
    op.drop_column("models", "deepseek_thinking_type")
    op.drop_column("models", "deepseek_reasoning_effort")
