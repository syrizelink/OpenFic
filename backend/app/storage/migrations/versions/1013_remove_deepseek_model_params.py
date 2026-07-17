"""remove deprecated DeepSeek model parameters and model tags

Revision ID: 1013
Revises: 1012
Create Date: 2026-07-17 13:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "1013"
down_revision: Union[str, Sequence[str], None] = "1012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE models
        SET temperature = COALESCE(temperature, 1.0),
            top_p = COALESCE(top_p, 1.0),
            top_k = COALESCE(top_k, 0),
            min_p = COALESCE(min_p, 0.0),
            top_a = COALESCE(top_a, 0.0),
            frequency_penalty = COALESCE(frequency_penalty, 0.0),
            presence_penalty = COALESCE(presence_penalty, 0.0),
            repetition_penalty = COALESCE(repetition_penalty, 1.0)
        WHERE task_type = 'llm'
        """
    )
    with op.batch_alter_table("models") as batch_op:
        batch_op.drop_column("deepseek_thinking_type")
        batch_op.drop_column("deepseek_reasoning_effort")
        batch_op.drop_column("tags")


def downgrade() -> None:
    import sqlalchemy as sa

    with op.batch_alter_table("models") as batch_op:
        batch_op.add_column(sa.Column("deepseek_reasoning_effort", sa.String(length=20)))
        batch_op.add_column(sa.Column("deepseek_thinking_type", sa.String(length=20)))
        batch_op.add_column(
            sa.Column("tags", sa.String(), nullable=False, server_default="[]")
        )
