"""remove context anchor columns from tasks and revisions

Revision ID: 050
Revises: 049
Create Date: 2026-05-31

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    task_columns = _column_names(bind, "tasks")
    revision_columns = _column_names(bind, "revisions")

    with op.batch_alter_table("tasks") as batch_op:
        if "current_context_anchor_order" in task_columns:
            batch_op.drop_column("current_context_anchor_order")

    with op.batch_alter_table("revisions") as batch_op:
        if "context_anchor_order" in revision_columns:
            batch_op.drop_column("context_anchor_order")


def downgrade() -> None:
    bind = op.get_bind()
    task_columns = _column_names(bind, "tasks")
    revision_columns = _column_names(bind, "revisions")

    with op.batch_alter_table("tasks") as batch_op:
        if "current_context_anchor_order" not in task_columns:
            batch_op.add_column(
                sa.Column(
                    "current_context_anchor_order",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )

    with op.batch_alter_table("revisions") as batch_op:
        if "context_anchor_order" not in revision_columns:
            batch_op.add_column(
                sa.Column(
                    "context_anchor_order",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
