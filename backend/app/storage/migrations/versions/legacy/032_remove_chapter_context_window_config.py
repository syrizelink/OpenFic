"""remove chapter context config table

Revision ID: 032
Revises: 031
Create Date: 2026-05-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop obsolete chapter context configuration table."""
    inspector = sa.inspect(op.get_bind())
    if "chapter_context_configs" not in inspector.get_table_names():
        return
    op.drop_index("ix_chapter_context_configs_project_id", table_name="chapter_context_configs")
    op.drop_table("chapter_context_configs")


def downgrade() -> None:
    """No downgrade path for removed runtime configuration."""
