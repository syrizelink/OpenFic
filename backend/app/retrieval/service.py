# -*- coding: utf-8 -*-
"""
OpenFic retrieval wrapper service.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.clients.embedding_client import EmbeddingClientLike
from app.models.repos import model_repo
from app.retrieval.engine import LanceDBRetrievalEngine
from app.retrieval.internal.common.naming import make_table_name
from app.retrieval.internal.contracts.index_contracts import (
    build_index_create_kwargs,
    contract_from_row,
    validate_contract_model,
)
from app.retrieval.types import (
    ChunkIndexResult,
    IndexDescription,
    IndexChunk,
    IndexDocument,
    RetrievalIndexContract,
)
from app.settings import settings
from app.storage.models.retrieval_index import RetrievalIndex
from app.storage.repos import retrieval_index_repo


class OpenFicRetrievalService:
    def __init__(self, *, base_dir: Path | None = None):
        self.base_dir = base_dir or (settings.static_dir / "lancedb")

    async def register_index(
        self,
        session: AsyncSession,
        index_key: str,
        contract: RetrievalIndexContract,
        *,
        replace_contract_if_needs_rebuild: bool = False,
    ) -> RetrievalIndex:
        await self._validate_contract(session, contract)
        existing = await retrieval_index_repo.get_by_index_key(session, index_key)
        if existing is None:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            return await retrieval_index_repo.create(
                session,
                **build_index_create_kwargs(
                    index_key=index_key,
                    table_name=make_table_name(index_key),
                    contract=contract,
                ),
            )

        if (
            existing.status == "needs_rebuild"
            and replace_contract_if_needs_rebuild
        ):
            await self._drop_index_table(existing)
            kwargs = build_index_create_kwargs(
                index_key=index_key,
                table_name=existing.table_name,
                contract=contract,
            )
            existing.status = kwargs["status"]
            existing.embedding_model_ref_id = kwargs["embedding_model_ref_id"]
            existing.embedding_model_id_snapshot = kwargs[
                "embedding_model_id_snapshot"
            ]
            existing.embedding_dimensions_snapshot = kwargs[
                "embedding_dimensions_snapshot"
            ]
            existing.distance_metric = kwargs["distance_metric"]
            existing.chunker_type = kwargs["chunker_type"]
            existing.chunk_size = kwargs["chunk_size"]
            existing.chunk_overlap = kwargs["chunk_overlap"]
            existing.filterable_fields_json = kwargs["filterable_fields_json"]
            existing.vector_index_type = kwargs["vector_index_type"]
            existing.vector_index_params_json = kwargs["vector_index_params_json"]
            existing.fts_index_params_json = kwargs["fts_index_params_json"]
            existing.schema_version = kwargs["schema_version"]
            existing.last_error = None
            return await retrieval_index_repo.update(session, existing)

        if contract_from_row(existing) != contract:
            raise ValueError("Index contract mismatch for existing index_key")
        return existing

    async def describe_index(
        self, session: AsyncSession, index_key: str
    ) -> IndexDescription:
        row = await self._get_index(session, index_key)
        return IndexDescription(
            index_key=row.index_key,
            table_name=row.table_name,
            status=row.status,
            contract=contract_from_row(row),
            last_error=row.last_error,
            last_build_at=row.last_build_at,
            last_ready_at=row.last_ready_at,
        )

    async def index_documents(
        self,
        session: AsyncSession,
        index_key: str,
        documents: list[IndexDocument],
        embedding_client: EmbeddingClientLike,
        *,
        max_consecutive_failures: int = 5,
        skip_chunking: bool = False,
    ):
        row = await self._get_index(session, index_key)
        if row.status not in {"registered", "ready", "failed"}:
            raise ValueError(f"Index {index_key} is not writable in status {row.status}")

        return await self._engine_for(row).index_documents(
            documents,
            embedding_client,
            skip_chunking=skip_chunking,
            max_consecutive_failures=max_consecutive_failures,
            on_status_change=lambda status, error: self._update_status(
                session, row, status=status, error=error
            ),
        )

    async def delete_document(
        self, session: AsyncSession, index_key: str, document_id: str
    ) -> None:
        row = await self._get_index(session, index_key)
        await self._engine_for(row).delete_document(document_id)

    async def index_chunk_batch(
        self,
        session: AsyncSession,
        index_key: str,
        chunks: list[IndexChunk],
        embedding_client: EmbeddingClientLike,
        *,
        replace_document_ids: set[str] | None = None,
    ) -> ChunkIndexResult:
        row = await self._get_index(session, index_key)
        if row.status not in {"registered", "building", "ready", "failed"}:
            raise ValueError(f"Index {index_key} is not writable in status {row.status}")
        await self._update_status(session, row, status="building", error=None)
        return await self._engine_for(row).index_chunks(
            chunks,
            embedding_client,
            replace_document_ids=replace_document_ids,
        )

    async def finalize_chunk_index(self, session: AsyncSession, index_key: str) -> None:
        row = await self._get_index(session, index_key)
        await self._engine_for(row).finalize_chunk_index()
        await self._update_status(session, row, status="ready", error=None)

    async def rebuild(
        self,
        session: AsyncSession,
        index_key: str,
        documents: list[IndexDocument],
        embedding_client: EmbeddingClientLike,
        *,
        skip_chunking: bool = False,
        max_consecutive_failures: int = 5,
    ):
        row = await self._get_index(session, index_key)
        return await self._engine_for(row).rebuild(
            documents,
            embedding_client,
            skip_chunking=skip_chunking,
            max_consecutive_failures=max_consecutive_failures,
            on_status_change=lambda status, error: self._update_status(
                session, row, status=status, error=error
            ),
        )

    async def rebuild_indexes(self, session: AsyncSession, index_key: str) -> None:
        row = await self._get_index(session, index_key)
        await self._engine_for(row).rebuild_indexes(
            on_status_change=lambda status, error: self._update_status(
                session, row, status=status, error=error
            )
        )

    async def query(
        self,
        session: AsyncSession,
        index_key: str,
        text: str,
        embedding_client: EmbeddingClientLike,
    ):
        row = await self._get_index(session, index_key)
        if row.status != "ready":
            raise ValueError(f"Index {index_key} is not ready")
        return self._engine_for(row).query(text, embedding_client)

    async def _get_index(
        self, session: AsyncSession, index_key: str
    ) -> RetrievalIndex:
        row = await retrieval_index_repo.get_by_index_key(session, index_key)
        if row is None:
            raise ValueError(f"Unknown index_key: {index_key}")
        return row

    def _engine_for(self, row: RetrievalIndex) -> LanceDBRetrievalEngine:
        return LanceDBRetrievalEngine(
            base_dir=self.base_dir,
            table_name=row.table_name,
            contract=contract_from_row(row),
        )

    async def _drop_index_table(self, row: RetrievalIndex) -> None:
        await self._engine_for(row)._drop_table()

    async def _update_status(
        self,
        session: AsyncSession,
        row: RetrievalIndex,
        *,
        status: str,
        error: str | None,
    ) -> None:
        now = datetime.now(UTC)
        row.status = status
        row.last_error = error
        row.last_build_at = now
        if status == "ready":
            row.last_ready_at = now
            row.last_error = None
        await retrieval_index_repo.update(session, row)

    async def _validate_contract(
        self, session: AsyncSession, contract: RetrievalIndexContract
    ) -> None:
        model = await model_repo.get_by_id(session, contract.embedding_model_ref_id)
        if model is None:
            raise NotFoundError(
                f"Embedding model {contract.embedding_model_ref_id} not found"
            )
        validate_contract_model(model, contract)
