"""rework summary staleness tracking

Revision ID: 036
Revises: 035
Create Date: 2026-05-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("DELETE FROM chapter_summaries")
    terminal_statuses = "('succeeded', 'failed', 'timeout', 'cancelled', 'skipped')"
    op.execute(
        "DELETE FROM background_job_items "
        "WHERE type IN ('chapter_summary', 'long_term_summary') "
        f"AND status NOT IN {terminal_statuses}"
    )
    op.execute(
        "DELETE FROM background_jobs "
        "WHERE type IN ('chapter_summary', 'long_term_summary') "
        f"AND status NOT IN {terminal_statuses}"
    )
    if _has_column("chapter_summaries", "source_updated_at"):
        op.drop_column("chapter_summaries", "source_updated_at")
    if not _has_column("chapter_summaries", "source_content_normalized"):
        op.add_column(
            "chapter_summaries",
            sa.Column("source_content_normalized", sa.Text(), nullable=False, server_default=""),
        )
    if not _has_column("chapter_summaries", "source_chapter_ids_json"):
        op.add_column(
            "chapter_summaries",
            sa.Column("source_chapter_ids_json", sa.Text(), nullable=False, server_default="[]"),
        )
    if not _has_column("chapter_summaries", "source_chapter_summary_signatures_json"):
        op.add_column(
            "chapter_summaries",
            sa.Column(
                "source_chapter_summary_signatures_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            ),
        )
    bind.execute(sa.text("UPDATE chapter_summaries SET status = 'ready' WHERE status = 'stale'"))


def downgrade() -> None:
    if not _has_column("chapter_summaries", "source_updated_at"):
        op.add_column("chapter_summaries", sa.Column("source_updated_at", sa.DateTime(), nullable=True))
    if _has_column("chapter_summaries", "source_chapter_summary_signatures_json"):
        op.drop_column("chapter_summaries", "source_chapter_summary_signatures_json")
    if _has_column("chapter_summaries", "source_chapter_ids_json"):
        op.drop_column("chapter_summaries", "source_chapter_ids_json")
    if _has_column("chapter_summaries", "source_content_normalized"):
        op.drop_column("chapter_summaries", "source_content_normalized")
