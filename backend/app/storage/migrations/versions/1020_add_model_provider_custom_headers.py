"""add encrypted custom headers to model providers

Revision ID: 1020
Revises: 1019
Create Date: 2026-08-26 10:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1020"
down_revision: Union[str, Sequence[str], None] = "1019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_providers",
        sa.Column(
            "custom_headers_encrypted",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("model_providers", "custom_headers_encrypted")
