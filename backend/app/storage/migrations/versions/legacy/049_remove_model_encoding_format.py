"""remove model encoding_format column

Revision ID: 049
Revises: 048
Create Date: 2026-05-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "models" not in inspector.get_table_names():
        return

    if "encoding_format" in _column_names(bind, "models"):
        op.drop_column("models", "encoding_format")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "models" not in inspector.get_table_names():
        return

    if "encoding_format" not in _column_names(bind, "models"):
        op.add_column(
            "models",
            sa.Column("encoding_format", sa.String(length=20), nullable=True),
        )
