"""add reasoning duration to agent run messages

Revision ID: 044
Revises: 043
Create Date: 2026-05-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "agent_run_messages")

    with op.batch_alter_table("agent_run_messages") as batch_op:
        if "reasoning_duration_ms" not in columns:
            batch_op.add_column(
                sa.Column("reasoning_duration_ms", sa.Integer(), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "agent_run_messages")

    with op.batch_alter_table("agent_run_messages") as batch_op:
        if "reasoning_duration_ms" in columns:
            batch_op.drop_column("reasoning_duration_ms")
