"""drop skill order_index column

Revision ID: 068
Revises: 067
Create Date: 2026-06-24

移除 skills 表中的 order_index，技能列表改为固定创建顺序，不再支持手动排序。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "068"
down_revision: Union[str, None] = "067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("skills") as batch_op:
        batch_op.drop_column("order_index")


def downgrade() -> None:
    with op.batch_alter_table("skills") as batch_op:
        batch_op.add_column(
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0")
        )
