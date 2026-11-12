"""Persist chapter Yjs documents.

Revision ID: 1031
Revises: 1030
"""

from importlib import import_module

from alembic import op
import sqlalchemy as sa

revision = "1031"
down_revision = "1030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # Earlier experimental builds used revision 1030 for collaboration. Main now
    # uses that number for quick prompts; complete both schemas without replacing
    # existing CRDT identities or chapter text.
    if not inspector.has_table("quick_prompts"):
        import_module(
            "app.storage.migrations.versions.1030_add_quick_prompts"
        ).upgrade()
    if inspector.has_table("chapter_collaboration"):
        return
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
