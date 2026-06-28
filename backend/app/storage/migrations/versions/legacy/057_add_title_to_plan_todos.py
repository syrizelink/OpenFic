"""add title to plan todos

Revision ID: 057
Revises: 056
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "057"
down_revision: Union[str, None] = "056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("plan_todos") as batch_op:
        batch_op.add_column(sa.Column("title", sa.Text(), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE plan_todos
            SET title = content
            WHERE title IS NULL OR trim(title) = ''
            """
        )
    )

    with op.batch_alter_table("plan_todos") as batch_op:
        batch_op.alter_column(
            "title",
            existing_type=sa.Text(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("plan_todos") as batch_op:
        batch_op.drop_column("title")
