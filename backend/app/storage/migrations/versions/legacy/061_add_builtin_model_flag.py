"""add builtin model flag

Revision ID: 061
Revises: 060
Create Date: 2026-06-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "061"
down_revision: Union[str, None] = "060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    models_cols = _column_names(bind, "models")
    if "is_builtin" not in models_cols:
        op.add_column(
            "models",
            sa.Column(
                "is_builtin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )

    providers_cols = _column_names(bind, "model_providers")
    if "is_builtin" not in providers_cols:
        op.add_column(
            "model_providers",
            sa.Column(
                "is_builtin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()

    providers_cols = _column_names(bind, "model_providers")
    if "is_builtin" in providers_cols:
        op.drop_column("model_providers", "is_builtin")

    models_cols = _column_names(bind, "models")
    if "is_builtin" in models_cols:
        op.drop_column("models", "is_builtin")
