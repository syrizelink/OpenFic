"""add task running state

Revision ID: 046
Revises: 045
Create Date: 2026-05-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    task_columns = _column_names(bind, "tasks")

    with op.batch_alter_table("tasks") as batch_op:
        if "is_running" not in task_columns:
            batch_op.add_column(
                sa.Column(
                    "is_running",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    task_columns = _column_names(bind, "tasks")

    with op.batch_alter_table("tasks") as batch_op:
        if "is_running" in task_columns:
            batch_op.drop_column("is_running")
