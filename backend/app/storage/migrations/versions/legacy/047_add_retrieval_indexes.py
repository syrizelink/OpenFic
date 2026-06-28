"""add retrieval indexes

Revision ID: 047
Revises: 046
Create Date: 2026-05-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "047"
down_revision: Union[str, None] = "046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "retrieval_indexes" not in tables:
        op.create_table(
            "retrieval_indexes",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("index_key", sa.String(length=200), nullable=False),
            sa.Column("table_name", sa.String(length=200), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="registered"),
            sa.Column("embedding_model_ref_id", sa.String(length=200), nullable=False),
            sa.Column("embedding_model_id_snapshot", sa.String(length=200), nullable=False),
            sa.Column("embedding_dimensions_snapshot", sa.Integer(), nullable=False),
            sa.Column("distance_metric", sa.String(length=20), nullable=False, server_default="cosine"),
            sa.Column("chunker_type", sa.String(length=50), nullable=False, server_default="recursive_character"),
            sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="800"),
            sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("filterable_fields_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("vector_index_type", sa.String(length=50), nullable=False, server_default="ivf_hnsw_sq"),
            sa.Column("vector_index_params_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("fts_index_params_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("last_build_at", sa.DateTime(), nullable=True),
            sa.Column("last_ready_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["embedding_model_ref_id"], ["models.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("index_key"),
        )
        op.create_index("ix_retrieval_indexes_index_key", "retrieval_indexes", ["index_key"])
        op.create_index("ix_retrieval_indexes_table_name", "retrieval_indexes", ["table_name"])
        op.create_index("ix_retrieval_indexes_status", "retrieval_indexes", ["status"])
        op.create_index(
            "ix_retrieval_indexes_embedding_model_ref_id",
            "retrieval_indexes",
            ["embedding_model_ref_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    if "retrieval_indexes" in tables:
        op.drop_index("ix_retrieval_indexes_embedding_model_ref_id", table_name="retrieval_indexes")
        op.drop_index("ix_retrieval_indexes_status", table_name="retrieval_indexes")
        op.drop_index("ix_retrieval_indexes_table_name", table_name="retrieval_indexes")
        op.drop_index("ix_retrieval_indexes_index_key", table_name="retrieval_indexes")
        op.drop_table("retrieval_indexes")
