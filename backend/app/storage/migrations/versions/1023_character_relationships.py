"""Add character relationships and graph positions.

Revision ID: 1023
Revises: 1022
"""

from alembic import op
import sqlalchemy as sa

revision = "1023"
down_revision = "1022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("characters") as batch_op:
        batch_op.add_column(sa.Column("graph_x", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("graph_y", sa.Float(), nullable=True))
    with op.batch_alter_table("revision_character_snapshots") as batch_op:
        batch_op.add_column(sa.Column("graph_x", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("graph_y", sa.Float(), nullable=True))
    op.create_table(
        "character_relationships",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("source_character_id", sa.String(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("target_character_id", sa.String(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.UniqueConstraint("project_id", "source_character_id", "target_character_id"),
        sa.CheckConstraint("source_character_id < target_character_id"),
    )
    for column in ("project_id", "source_character_id", "target_character_id"):
        op.create_index(f"ix_character_relationships_{column}", "character_relationships", [column])
    op.create_table(
        "revision_character_relationship_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("revision_id", sa.String(), sa.ForeignKey("revisions.id"), nullable=False),
        sa.Column("relationship_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("exists", sa.Boolean(), nullable=False),
        sa.Column("source_character_id", sa.String(), nullable=True),
        sa.Column("target_character_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.UniqueConstraint("revision_id", "relationship_id"),
    )
    for column in ("revision_id", "relationship_id", "project_id"):
        op.create_index(f"ix_revision_character_relationship_snapshots_{column}", "revision_character_relationship_snapshots", [column])


def downgrade() -> None:
    op.drop_table("revision_character_relationship_snapshots")
    op.drop_table("character_relationships")
    with op.batch_alter_table("revision_character_snapshots") as batch_op:
        batch_op.drop_column("graph_y")
        batch_op.drop_column("graph_x")
    with op.batch_alter_table("characters") as batch_op:
        batch_op.drop_column("graph_y")
        batch_op.drop_column("graph_x")
