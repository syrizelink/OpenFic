# -*- coding: utf-8 -*-
"""
PyArrow schema helpers for retrieval tables.
"""

import pyarrow as pa

from app.retrieval.types import FilterableFieldType, RetrievalIndexContract


def field_type_to_arrow(field_type: FilterableFieldType):
    if field_type == FilterableFieldType.STRING:
        return pa.string()
    if field_type == FilterableFieldType.INTEGER:
        return pa.int64()
    if field_type == FilterableFieldType.FLOAT:
        return pa.float64()
    if field_type == FilterableFieldType.BOOLEAN:
        return pa.bool_()
    raise ValueError(f"Unsupported filterable field type: {field_type}")


def build_chunk_table_schema(contract: RetrievalIndexContract) -> pa.Schema:
    fields = [
        pa.field("chunk_id", pa.string()),
        pa.field("document_id", pa.string()),
        pa.field("chunk_index", pa.int32()),
        pa.field("text", pa.string()),
        pa.field("raw_text", pa.string()),
        pa.field(
            "vector",
            pa.list_(pa.float32(), contract.embedding_dimensions_snapshot),
        ),
        pa.field("metadata", pa.string()),
    ]
    for field in contract.filterable_fields:
        fields.append(pa.field(field.name, field_type_to_arrow(field.field_type)))
    return pa.schema(fields)
