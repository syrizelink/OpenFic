"""add skill reference docs and drop skill id

Revision ID: 1007
Revises: 1006
Create Date: 2026-07-07 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlmodel import AutoString


# revision identifiers, used by Alembic.
revision: str = "1007"
down_revision: Union[str, Sequence[str], None] = "1006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "skill_reference_docs",
        sa.Column("id", AutoString(), nullable=False),
        sa.Column("skill_db_id", AutoString(), nullable=False),
        sa.Column("title", AutoString(length=200), nullable=False),
        sa.Column("content", AutoString(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["skill_db_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_skill_reference_docs_skill_db_id"),
        "skill_reference_docs",
        ["skill_db_id"],
        unique=False,
    )

    with op.batch_alter_table("skills") as batch_op:
        batch_op.drop_index("ix_skills_skill_id")
        batch_op.drop_column("skill_id")

    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.alter_column(
            "enabled_skill_ids_json",
            new_column_name="enabled_skill_names_json",
            existing_type=sa.JSON(),
            nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("agent_definitions") as batch_op:
        batch_op.alter_column(
            "enabled_skill_names_json",
            new_column_name="enabled_skill_ids_json",
            existing_type=sa.JSON(),
            nullable=False,
        )

    with op.batch_alter_table("skills") as batch_op:
        batch_op.add_column(sa.Column("skill_id", AutoString(length=100), nullable=False, server_default=""))
        batch_op.create_index("ix_skills_skill_id", ["skill_id"], unique=False)

    op.drop_index(
        op.f("ix_skill_reference_docs_skill_db_id"),
        table_name="skill_reference_docs",
    )
    op.drop_table("skill_reference_docs")