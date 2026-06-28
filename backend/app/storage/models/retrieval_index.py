# -*- coding: utf-8 -*-
"""
RetrievalIndex 数据模型。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class RetrievalIndex(SQLModel, table=True):
    """检索索引契约模型。"""

    __tablename__ = "retrieval_indexes"

    id: str = Field(default_factory=generate_id, primary_key=True)
    index_key: str = Field(unique=True, index=True, max_length=200)
    table_name: str = Field(index=True, max_length=200)
    status: str = Field(default="registered", max_length=20, index=True)

    embedding_model_ref_id: str = Field(
        foreign_key="models.id", index=True, max_length=200
    )
    embedding_model_id_snapshot: str = Field(max_length=200)
    embedding_dimensions_snapshot: int = Field(ge=1)
    distance_metric: str = Field(default="cosine", max_length=20)

    chunker_type: str = Field(default="recursive_character", max_length=50)
    chunk_size: int = Field(default=800, ge=1)
    chunk_overlap: int = Field(default=100, ge=0)

    filterable_fields_json: str = Field(default="[]")
    vector_index_type: str = Field(default="ivf_hnsw_sq", max_length=50)
    vector_index_params_json: str = Field(default="{}")
    fts_index_params_json: str = Field(default="{}")
    schema_version: int = Field(default=1, ge=1)

    last_error: str | None = Field(default=None)
    last_build_at: datetime | None = Field(default=None)
    last_ready_at: datetime | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
