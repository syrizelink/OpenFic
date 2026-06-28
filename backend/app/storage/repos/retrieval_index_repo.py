# -*- coding: utf-8 -*-
"""
RetrievalIndex Repository - 检索索引契约数据访问层。
"""

from datetime import UTC, datetime

from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.retrieval_index import RetrievalIndex


async def create(
    session: AsyncSession,
    *,
    index_key: str,
    table_name: str,
    status: str,
    embedding_model_ref_id: str,
    embedding_model_id_snapshot: str,
    embedding_dimensions_snapshot: int,
    distance_metric: str,
    chunker_type: str,
    chunk_size: int,
    chunk_overlap: int,
    filterable_fields_json: str,
    vector_index_type: str,
    vector_index_params_json: str,
    fts_index_params_json: str,
    schema_version: int,
) -> RetrievalIndex:
    row = RetrievalIndex(
        index_key=index_key,
        table_name=table_name,
        status=status,
        embedding_model_ref_id=embedding_model_ref_id,
        embedding_model_id_snapshot=embedding_model_id_snapshot,
        embedding_dimensions_snapshot=embedding_dimensions_snapshot,
        distance_metric=distance_metric,
        chunker_type=chunker_type,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        filterable_fields_json=filterable_fields_json,
        vector_index_type=vector_index_type,
        vector_index_params_json=vector_index_params_json,
        fts_index_params_json=fts_index_params_json,
        schema_version=schema_version,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def get_by_index_key(
    session: AsyncSession, index_key: str
) -> RetrievalIndex | None:
    result = await session.execute(
        select(RetrievalIndex).where(col(RetrievalIndex.index_key) == index_key)
    )
    return result.scalar_one_or_none()


async def get_by_embedding_model_ref_id(
    session: AsyncSession, model_id: str
) -> list[RetrievalIndex]:
    result = await session.execute(
        select(RetrievalIndex).where(
            col(RetrievalIndex.embedding_model_ref_id) == model_id
        )
    )
    return list(result.scalars().all())


async def exists_by_embedding_model_ref_id(
    session: AsyncSession, model_id: str
) -> bool:
    rows = await get_by_embedding_model_ref_id(session, model_id)
    return len(rows) > 0


async def update(session: AsyncSession, row: RetrievalIndex) -> RetrievalIndex:
    row.updated_at = datetime.now(UTC)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def mark_all_needs_rebuild(session: AsyncSession) -> None:
    await session.execute(
        sql_update(RetrievalIndex).values(
            status="needs_rebuild",
            last_error=None,
            updated_at=datetime.now(UTC),
        )
    )
    await session.flush()
