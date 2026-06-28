# -*- coding: utf-8 -*-
"""
Types for retrieval subsystem.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


JSONScalar = str | int | float | bool | None


class FilterableFieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


class FilterableField(BaseModel):
    name: str
    field_type: FilterableFieldType


class RetrievalIndexContract(BaseModel):
    embedding_model_ref_id: str
    embedding_model_id_snapshot: str
    embedding_dimensions_snapshot: int = Field(ge=1)
    distance_metric: Literal["l2", "cosine", "dot"] = "cosine"
    chunker_type: str = "recursive_character"
    chunk_size: int = Field(default=800, ge=1)
    chunk_overlap: int = Field(default=100, ge=0)
    filterable_fields: list[FilterableField] = Field(default_factory=list)
    vector_index_type: str = "ivf_hnsw_sq"
    vector_index_params: dict[str, Any] = Field(default_factory=dict)
    fts_index_params: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = Field(default=1, ge=1)


class IndexDocument(BaseModel):
    document_id: str
    text: str | None = None
    chunks: list[str] | None = None
    attributes: dict[str, JSONScalar] | None = None
    metadata: dict[str, JSONScalar | list[JSONScalar]] | None = None


class DocumentIndexSuccess(BaseModel):
    document_id: str
    chunk_count: int


class DocumentIndexFailure(BaseModel):
    document_id: str
    error: str


class BatchIndexResult(BaseModel):
    total_documents: int
    succeeded_count: int
    failed_count: int
    stopped_early: bool = False
    stop_reason: str | None = None
    succeeded: list[DocumentIndexSuccess] = Field(default_factory=list)
    failed: list[DocumentIndexFailure] = Field(default_factory=list)


class ChunkSearchResult(BaseModel):
    document_id: str
    chunk_id: str
    chunk_index: int
    text: str
    metadata: dict[str, Any]
    score: float
    vector_score: float | None = None
    bm25_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    matched_by: Literal["vector", "bm25", "hybrid"]


class IndexDescription(BaseModel):
    index_key: str
    table_name: str
    status: str
    contract: RetrievalIndexContract
    last_error: str | None = None
    last_build_at: datetime | None = None
    last_ready_at: datetime | None = None
