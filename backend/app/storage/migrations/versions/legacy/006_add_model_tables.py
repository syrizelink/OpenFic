"""Add model and model_provider tables

Revision ID: 006
Revises: 005
Create Date: 2026-01-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create model_providers and models tables."""
    from sqlalchemy import inspect
    
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Create model_providers table if it doesn't exist
    if "model_providers" not in existing_tables:
        op.create_table(
            "model_providers",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("url", sa.String(length=500), nullable=False),
            sa.Column("api_key_encrypted", sa.String(length=1000), nullable=False),
            sa.Column("provider_type", sa.String(length=50), nullable=False),
            sa.Column("icon_type", sa.String(length=20), nullable=False),
            sa.Column("custom_icon", sa.String(length=10000), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    # Create models table if it doesn't exist
    if "models" not in existing_tables:
        op.create_table(
            "models",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("remark", sa.String(length=500), nullable=False),
            sa.Column("provider_id", sa.String(), nullable=False),
            sa.Column("model_id", sa.String(length=200), nullable=False),
            sa.Column("tags", sa.String(), nullable=False),
            sa.Column("temperature", sa.Float(), nullable=True),
            sa.Column("top_p", sa.Float(), nullable=True),
            sa.Column("top_k", sa.Integer(), nullable=True),
            sa.Column("min_p", sa.Float(), nullable=True),
            sa.Column("top_a", sa.Float(), nullable=True),
            sa.Column("frequency_penalty", sa.Float(), nullable=True),
            sa.Column("presence_penalty", sa.Float(), nullable=True),
            sa.Column("repetition_penalty", sa.Float(), nullable=True),
            sa.Column("max_tokens", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["provider_id"],
                ["model_providers.id"],
            ),
        )

    # Create indexes if models table was just created or index doesn't exist
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("models")] if "models" in existing_tables else []
    if "ix_models_provider_id" not in existing_indexes:
        op.create_index(
            op.f("ix_models_provider_id"), "models", ["provider_id"], unique=False
        )


def downgrade() -> None:
    """Drop model_providers and models tables."""
    op.drop_index(op.f("ix_models_provider_id"), table_name="models")
    op.drop_table("models")
    op.drop_table("model_providers")
