"""add retrieval chapter index states

Revision ID: 060
Revises: 059
Create Date: 2026-06-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "060"
down_revision: Union[str, None] = "059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if "retrieval_chapter_index_states" in _table_names(bind):
        return

    op.create_table(
        "retrieval_chapter_index_states",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=False),
        sa.Column("index_key", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="not_indexed",
        ),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("embedding_model_ref_id", sa.String(length=200), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("item_id", sa.String(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
        sa.ForeignKeyConstraint(["embedding_model_ref_id"], ["models.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["background_jobs.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["background_job_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "chapter_id",
            "index_key",
            name="uq_retrieval_chapter_index_state",
        ),
    )
    for column in (
        "project_id",
        "chapter_id",
        "index_key",
        "status",
        "embedding_model_ref_id",
        "job_id",
        "item_id",
        "indexed_at",
        "updated_at",
    ):
        op.create_index(
            f"ix_retrieval_chapter_index_states_{column}",
            "retrieval_chapter_index_states",
            [column],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "retrieval_chapter_index_states" not in _table_names(bind):
        return
    for column in (
        "updated_at",
        "indexed_at",
        "item_id",
        "job_id",
        "embedding_model_ref_id",
        "status",
        "index_key",
        "chapter_id",
        "project_id",
    ):
        op.drop_index(
            f"ix_retrieval_chapter_index_states_{column}",
            table_name="retrieval_chapter_index_states",
        )
    op.drop_table("retrieval_chapter_index_states")
