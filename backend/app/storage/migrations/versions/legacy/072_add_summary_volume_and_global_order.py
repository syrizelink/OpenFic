"""add summary volume id and backfill global reading order

Revision ID: 072
Revises: 071
Create Date: 2026-06-25 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "072"
down_revision: Union[str, None] = "071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chapter_summaries") as batch_op:
        batch_op.add_column(sa.Column("volume_id", sa.String(), nullable=True))
        batch_op.create_index(
            "ix_chapter_summaries_volume_id", ["volume_id"]
        )
        batch_op.create_foreign_key(
            "fk_chapter_summaries_volume_id_volumes",
            "volumes",
            ["volume_id"],
            ["id"],
        )

    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            WITH global_orders AS (
                SELECT c.id AS chapter_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY c.project_id
                           ORDER BY v."order" ASC, c."order" ASC
                       ) AS global_order
                FROM chapters c
                JOIN volumes v ON c.volume_id = v.id
            )
            UPDATE chapter_summaries
            SET volume_id = (
                    SELECT c.volume_id FROM chapters c
                    WHERE c.id = chapter_summaries.chapter_id
                ),
                chapter_order = (
                    SELECT go.global_order FROM global_orders go
                    WHERE go.chapter_id = chapter_summaries.chapter_id
                ),
                start_order = (
                    SELECT go.global_order FROM global_orders go
                    WHERE go.chapter_id = chapter_summaries.chapter_id
                ),
                end_order = (
                    SELECT go.global_order FROM global_orders go
                    WHERE go.chapter_id = chapter_summaries.chapter_id
                )
            WHERE summary_type = 'chapter'
            """
        )
    )

    bind.execute(
        sa.text(
            """
            WITH global_orders AS (
                SELECT c.id AS chapter_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY c.project_id
                           ORDER BY v."order" ASC, c."order" ASC
                       ) AS global_order
                FROM chapters c
                JOIN volumes v ON c.volume_id = v.id
            )
            UPDATE chapter_summaries
            SET start_order = (
                    SELECT MIN(go.global_order)
                    FROM json_each(chapter_summaries.source_chapter_ids_json) AS je
                    JOIN global_orders go
                        ON go.chapter_id = je.value
                ),
                end_order = (
                    SELECT MAX(go.global_order)
                    FROM json_each(chapter_summaries.source_chapter_ids_json) AS je
                    JOIN global_orders go
                        ON go.chapter_id = je.value
                )
            WHERE summary_type = 'long_term'
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("chapter_summaries") as batch_op:
        batch_op.drop_column("volume_id")
