"""rebuild chapter summaries for structured background generation

Revision ID: 029
Revises: 028
Create Date: 2026-05-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_chapter_summaries_chapter_id", table_name="chapter_summaries")
    op.drop_index("ix_chapter_summaries_summary_type", table_name="chapter_summaries")
    op.drop_index("ix_chapter_summaries_project_id", table_name="chapter_summaries")
    op.drop_table("chapter_summaries")

    op.create_table(
        "chapter_summaries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("summary_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="not_generated"),
        sa.Column("chapter_id", sa.String(), nullable=True),
        sa.Column("chapter_order", sa.Integer(), nullable=True),
        sa.Column("start_order", sa.Integer(), nullable=True),
        sa.Column("end_order", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.String(), nullable=False, server_default=""),
        sa.Column("end_time", sa.String(), nullable=False, server_default=""),
        sa.Column("characters_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("locations_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(), nullable=True),
        sa.Column("model_id", sa.String(length=200), nullable=True),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "project_id",
        "summary_type",
        "status",
        "chapter_id",
        "chapter_order",
        "start_order",
        "end_order",
        "job_id",
    ):
        op.create_index(f"ix_chapter_summaries_{column}", "chapter_summaries", [column])


def downgrade() -> None:
    for column in (
        "job_id",
        "end_order",
        "start_order",
        "chapter_order",
        "chapter_id",
        "status",
        "summary_type",
        "project_id",
    ):
        op.drop_index(f"ix_chapter_summaries_{column}", table_name="chapter_summaries")
    op.drop_table("chapter_summaries")

    op.create_table(
        "chapter_summaries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("summary_type", sa.String(length=20), nullable=False),
        sa.Column("chapter_id", sa.String(), nullable=True),
        sa.Column("start_order", sa.Integer(), nullable=True),
        sa.Column("end_order", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chapter_summaries_project_id", "chapter_summaries", ["project_id"])
    op.create_index("ix_chapter_summaries_summary_type", "chapter_summaries", ["summary_type"])
    op.create_index("ix_chapter_summaries_chapter_id", "chapter_summaries", ["chapter_id"])
