# -*- coding: utf-8 -*-
"""
Helpers for retrieval index contract persistence and validation.
"""

import json
from typing import Any, Literal, cast

from app.models.entities.model import Model
from app.retrieval.types import RetrievalIndexContract
from app.storage.models.retrieval_index import RetrievalIndex

_ALLOWED_DISTANCE_METRICS = frozenset({"l2", "cosine", "dot"})


def _parse_distance_metric(value: str) -> Literal["l2", "cosine", "dot"]:
    if value not in _ALLOWED_DISTANCE_METRICS:
        raise ValueError(f"Unsupported distance_metric: {value}")
    return cast(Literal["l2", "cosine", "dot"], value)


def build_index_create_kwargs(
    *, index_key: str, table_name: str, contract: RetrievalIndexContract
) -> dict[str, Any]:
    return {
        "index_key": index_key,
        "table_name": table_name,
        "status": "registered",
        "embedding_model_ref_id": contract.embedding_model_ref_id,
        "embedding_model_id_snapshot": contract.embedding_model_id_snapshot,
        "embedding_dimensions_snapshot": contract.embedding_dimensions_snapshot,
        "distance_metric": contract.distance_metric,
        "chunker_type": contract.chunker_type,
        "chunk_size": contract.chunk_size,
        "chunk_overlap": contract.chunk_overlap,
        "filterable_fields_json": json.dumps(
            [field.model_dump() for field in contract.filterable_fields],
            ensure_ascii=False,
        ),
        "vector_index_type": contract.vector_index_type,
        "vector_index_params_json": json.dumps(
            contract.vector_index_params, ensure_ascii=False
        ),
        "fts_index_params_json": json.dumps(
            contract.fts_index_params, ensure_ascii=False
        ),
        "schema_version": contract.schema_version,
    }


def contract_from_row(row: RetrievalIndex) -> RetrievalIndexContract:
    return RetrievalIndexContract(
        embedding_model_ref_id=row.embedding_model_ref_id,
        embedding_model_id_snapshot=row.embedding_model_id_snapshot,
        embedding_dimensions_snapshot=row.embedding_dimensions_snapshot,
        distance_metric=_parse_distance_metric(row.distance_metric),
        chunker_type=row.chunker_type,
        chunk_size=row.chunk_size,
        chunk_overlap=row.chunk_overlap,
        filterable_fields=json.loads(row.filterable_fields_json),
        vector_index_type=row.vector_index_type,
        vector_index_params=json.loads(row.vector_index_params_json),
        fts_index_params=json.loads(row.fts_index_params_json),
        schema_version=row.schema_version,
    )


def validate_contract_model(
    model: Model,
    contract: RetrievalIndexContract,
) -> None:
    if model.task_type != "embedding":
        raise ValueError("Retrieval index contract requires an embedding model")
    if model.model_id != contract.embedding_model_id_snapshot:
        raise ValueError("Embedding model_id snapshot mismatch")
    if model.dimensions != contract.embedding_dimensions_snapshot:
        raise ValueError("Embedding dimensions snapshot mismatch")
