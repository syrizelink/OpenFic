# -*- coding: utf-8 -*-
"""
Validation helpers for retrieval input and query construction.
"""

from typing import Any

from app.retrieval.types import (
    FilterableField,
    FilterableFieldType,
    IndexDocument,
    RetrievalIndexContract,
)


def validate_metadata(metadata: dict[str, Any] | None) -> None:
    if metadata is None:
        return
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a dictionary")
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise ValueError("metadata keys must be strings")
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, (str, int, float, bool)) and item is not None:
                    raise ValueError("metadata list values must be JSON scalars")
        elif not isinstance(value, (str, int, float, bool)) and value is not None:
            raise ValueError("metadata values must be JSON scalars or scalar lists")


def check_attribute_type(value: Any, field: FilterableField) -> None:
    if value is None:
        return
    if field.field_type == FilterableFieldType.STRING and not isinstance(value, str):
        raise ValueError(f"Field {field.name} must be a string")
    if field.field_type == FilterableFieldType.INTEGER and (
        isinstance(value, bool) or not isinstance(value, int)
    ):
        raise ValueError(f"Field {field.name} must be an integer")
    if field.field_type == FilterableFieldType.FLOAT and (
        isinstance(value, bool) or not isinstance(value, (int, float))
    ):
        raise ValueError(f"Field {field.name} must be a float")
    if field.field_type == FilterableFieldType.BOOLEAN and not isinstance(value, bool):
        raise ValueError(f"Field {field.name} must be a boolean")


def validate_attributes(
    contract: RetrievalIndexContract, attributes: dict[str, Any]
) -> None:
    declared = {field.name: field for field in contract.filterable_fields}
    for name in attributes:
        if name not in declared:
            raise ValueError(f"Undeclared filterable field: {name}")
    for field in contract.filterable_fields:
        check_attribute_type(attributes.get(field.name), field)


def validate_document(
    contract: RetrievalIndexContract,
    document: IndexDocument,
    *,
    skip_chunking: bool,
) -> None:
    if not document.document_id.strip():
        raise ValueError("document_id must be a non-empty string")
    if skip_chunking:
        if document.text is not None:
            raise ValueError("text must be omitted when skip_chunking=True")
        if not document.chunks:
            raise ValueError("chunks are required when skip_chunking=True")
        for chunk in document.chunks:
            if not isinstance(chunk, str) or not chunk.strip():
                raise ValueError("chunks must contain non-empty strings")
            if len(chunk.strip()) > contract.chunk_size:
                raise ValueError("Chunk exceeds registered chunk_size")
    else:
        if document.text is None:
            raise ValueError("text is required when skip_chunking=False")
        if document.chunks is not None:
            raise ValueError("chunks must be omitted when skip_chunking=False")


def validate_batch(
    contract: RetrievalIndexContract,
    documents: list[IndexDocument],
    *,
    skip_chunking: bool,
) -> None:
    if len({doc.document_id for doc in documents}) != len(documents):
        raise ValueError("Duplicate document_id values are not allowed")
    for document in documents:
        validate_document(contract, document, skip_chunking=skip_chunking)
        validate_attributes(contract, document.attributes or {})
        validate_metadata(document.metadata)


def validate_embedding_client(
    contract: RetrievalIndexContract, embedding_client: Any
) -> None:
    config = getattr(embedding_client, "config", None)
    if config is None:
        raise ValueError("embedding_client must expose config")
    if getattr(config, "model_id", None) != contract.embedding_model_id_snapshot:
        raise ValueError("Embedding model_id mismatch")
    if getattr(config, "dimensions", None) != contract.embedding_dimensions_snapshot:
        raise ValueError("Embedding dimensions mismatch")


def validate_query_filter(
    contract: RetrievalIndexContract, field_name: str, value: Any
) -> None:
    field = next(
        (item for item in contract.filterable_fields if item.name == field_name),
        None,
    )
    if field is None:
        raise ValueError(f"Undeclared filterable field: {field_name}")
    check_attribute_type(value, field)
