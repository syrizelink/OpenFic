"""Persist chapter Yjs documents.

Revision ID: 1030
Revises: 1029
"""

from alembic import op
import sqlalchemy as sa

revision = "1030"
down_revision = "1029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chapter_collaboration",
        sa.Column("chapter_id", sa.String(), nullable=False),
        sa.Column("epoch", sa.String(), nullable=False),
        sa.Column("state", sa.LargeBinary(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chapter_id"),
    )


def downgrade() -> None:
    op.drop_table("chapter_collaboration")
