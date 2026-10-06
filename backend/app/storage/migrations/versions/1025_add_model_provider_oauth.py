"""Add encrypted provider credentials and reusable OAuth registrations.

Revision ID: 1025
Revises: 1024
Create Date: 2026-10-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1025"
down_revision: Union[str, Sequence[str], None] = "1024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_providers",
        sa.Column(
            "credentials_encrypted",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.create_table(
        "model_provider_oauth_registrations",
        sa.Column("provider_type", sa.String(255), nullable=False),
        sa.Column("issuer", sa.String(255), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("provider_id", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("provider_type", "issuer", "client_id"),
    )
    op.create_index(
        "ix_model_provider_oauth_registrations_provider_id",
        "model_provider_oauth_registrations", ["provider_id"],
    )


def downgrade() -> None:
    op.drop_table("model_provider_oauth_registrations")
    with op.batch_alter_table("model_providers") as batch:
        batch.drop_column("credentials_encrypted")
