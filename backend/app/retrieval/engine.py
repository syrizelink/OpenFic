# -*- coding: utf-8 -*-
"""
Core LanceDB retrieval engine.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lancedb  # type: ignore[import-untyped]
from lancedb.index import FTS, BTree, IvfHnswSq  # type: ignore[import-untyped]

from app.core.errors import ValidationError
from app.retrieval.internal.common.codec import serialize_metadata
from app.retrieval.internal.common.naming import make_table_name, quote_sql
from app.retrieval.internal.indexing.chunking import RecursiveCharacterChunker
from app.retrieval.internal.indexing.table_schema import build_chunk_table_schema
from app.retrieval.internal.query.builder import RetrievalQueryBuilder
from app.retrieval.internal.validation import (
    validate_batch,
    validate_embedding_client,
)
from app.retrieval.types import (
    BatchIndexResult,
    ChunkIndexResult,
    DocumentIndexFailure,
    DocumentIndexSuccess,
    IndexChunk,
    IndexDocument,
    RetrievalIndexContract,
)


@dataclass
class ChunkPiece:
    """单个分块：raw_text 为正文（回传用），indexed_text 为注入前缀后用于 embedding/FTS 的文本。"""

    raw_text: str
    indexed_text: str


class LanceDBRetrievalEngine:
    def __init__(
        self,
        *,
        base_dir: Path,
        table_name: str,
        contract: RetrievalIndexContract,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.table_name = table_name
        self.contract = contract

    @property
    def db_uri(self) -> str:
        return str(self.base_dir)

    async def index_documents(
        self,
        documents: list[IndexDocument],
        embedding_client: Any,
        *,
        skip_chunking: bool = False,
        max_consecutive_failures: int = 5,
        on_status_change: Callable[[str, str | None], Any] | None = None,
    ) -> BatchIndexResult:
        validate_embedding_client(self.contract, embedding_client)
        validate_batch(self.contract, documents, skip_chunking=skip_chunking)

        if on_status_change is not None:
            maybe_awaitable = on_status_change("building", None)
            if asyncio.iscoroutine(maybe_awaitable):
                await maybe_awaitable

        await self._ensure_table()
        table = await self._open_table()

        # Phase 1: Chunk all documents
        doc_chunks: list[tuple[IndexDocument, list[ChunkPiece]]] = []
        failures: list[DocumentIndexFailure] = []
        consecutive_failures = 0

        for document in documents:
            try:
                chunks = self._chunk_document(document, skip_chunking=skip_chunking)
                if not chunks:
                    raise ValueError("Document produced no chunks")
                doc_chunks.append((document, chunks))
                consecutive_failures = 0
            except Exception as exc:
                failures.append(
                    DocumentIndexFailure(
                        document_id=document.document_id,
                        error=str(exc),
                    )
                )
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    break

        # Phase 2: Batch embed all chunks (使用注入前缀后的 indexed_text)
        successes: list[DocumentIndexSuccess] = []
        embedding_failed = False

        if doc_chunks:
            all_chunks = [
                piece.indexed_text for _, chunks in doc_chunks for piece in chunks
            ]
            try:
                response = await embedding_client.embed(all_chunks)
                if len(response.embeddings) != len(all_chunks):
                    raise ValidationError("Embedding response size mismatch")
            except Exception as exc:
                for doc, _ in doc_chunks:
                    failures.append(
                        DocumentIndexFailure(
                            document_id=doc.document_id,
                            error=str(exc),
                        )
                    )
                embedding_failed = True

        # Phase 3: Write per document
        if not embedding_failed and doc_chunks:
            write_lock = asyncio.Lock()
            did_add_rows = False
            vector_idx = 0

            for document, chunks in doc_chunks:
                doc_vectors = response.embeddings[
                    vector_idx : vector_idx + len(chunks)
                ]
                vector_idx += len(chunks)

                try:
                    rows = self._build_rows(document, chunks, doc_vectors)
                except Exception as exc:
                    failures.append(
                        DocumentIndexFailure(
                            document_id=document.document_id,
                            error=str(exc),
                        )
                    )
                    continue

                async with write_lock:
                    try:
                        await table.delete(
                            f"document_id = '{quote_sql(document.document_id)}'"
                        )
                        if rows:
                            await table.add(rows)
                            did_add_rows = True
                        successes.append(
                            DocumentIndexSuccess(
                                document_id=document.document_id,
                                chunk_count=len(rows),
                            )
                        )
                    except Exception as exc:
                        failures.append(
                            DocumentIndexFailure(
                                document_id=document.document_id,
                                error=str(exc),
                            )
                        )

            if did_add_rows:
                await self._ensure_indexes(table)
                await table.optimize()

        if on_status_change is not None:
            if successes:
                maybe_awaitable = on_status_change("ready", None)
            else:
                maybe_awaitable = on_status_change(
                    "failed",
                    failures[-1].error if failures else "No documents succeeded",
                )
            if asyncio.iscoroutine(maybe_awaitable):
                await maybe_awaitable

        stop_reason = (
            f"Reached {max_consecutive_failures} consecutive failures"
            if consecutive_failures >= max_consecutive_failures
            else None
        )
        return BatchIndexResult(
            total_documents=len(documents),
            succeeded_count=len(successes),
            failed_count=len(failures),
            stopped_early=consecutive_failures >= max_consecutive_failures,
            stop_reason=stop_reason,
            succeeded=successes,
            failed=failures,
        )

    async def delete_document(self, document_id: str) -> None:
        table = await self._open_table()
        await table.delete(f"document_id = '{quote_sql(document_id)}'")

    async def index_chunks(
        self,
        chunks: list[IndexChunk],
        embedding_client: Any,
        *,
        replace_document_ids: set[str] | None = None,
    ) -> ChunkIndexResult:
        """Embed and append a bounded chunk batch without rebuilding table indexes."""
        validate_embedding_client(self.contract, embedding_client)
        if not chunks:
            return ChunkIndexResult(succeeded_chunk_count=0)

        await self._ensure_table()
        table = await self._open_table()
        response = await embedding_client.embed([chunk.indexed_text for chunk in chunks])
        if len(response.embeddings) != len(chunks):
            raise ValidationError("Embedding response size mismatch")

        for document_id in replace_document_ids or set():
            await table.delete(f"document_id = '{quote_sql(document_id)}'")

        rows = [
            self._build_chunk_row(chunk, vector)
            for chunk, vector in zip(chunks, response.embeddings, strict=True)
        ]
        await table.add(rows)
        return ChunkIndexResult(succeeded_chunk_count=len(rows))

    async def finalize_chunk_index(self) -> None:
        """Build search indexes once after all bounded chunk writes succeed."""
        table = await self._open_table()
        await self._ensure_indexes(table)
        await table.optimize()

    async def rebuild(
        self,
        documents: list[IndexDocument],
        embedding_client: Any,
        *,
        skip_chunking: bool = False,
        max_consecutive_failures: int = 5,
        on_status_change: Callable[[str, str | None], Any] | None = None,
    ) -> BatchIndexResult:
        validate_embedding_client(self.contract, embedding_client)
        validate_batch(self.contract, documents, skip_chunking=skip_chunking)
        await self._drop_table()
        return await self.index_documents(
            documents,
            embedding_client,
            skip_chunking=skip_chunking,
            max_consecutive_failures=max_consecutive_failures,
            on_status_change=on_status_change,
        )

    async def rebuild_indexes(
        self,
        *,
        on_status_change: Callable[[str, str | None], Any] | None = None,
    ) -> None:
        table = await self._open_table()
        if on_status_change is not None:
            maybe_awaitable = on_status_change("building", None)
            if asyncio.iscoroutine(maybe_awaitable):
                await maybe_awaitable
        await self._ensure_indexes(table, force_rebuild=True)
        if on_status_change is not None:
            maybe_awaitable = on_status_change("ready", None)
            if asyncio.iscoroutine(maybe_awaitable):
                await maybe_awaitable

    def query(self, text: str, embedding_client: Any) -> RetrievalQueryBuilder:
        validate_embedding_client(self.contract, embedding_client)
        return RetrievalQueryBuilder(
            engine=self,
            query_text=text,
            embedding_client=embedding_client,
        )

    async def _connect(self):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return await lancedb.connect_async(self.db_uri)

    async def _ensure_table(self) -> None:
        db = await self._connect()
        names = list((await db.list_tables()).tables)
        if self.table_name not in names:
            await db.create_table(
                self.table_name,
                schema=build_chunk_table_schema(self.contract),
                mode="create",
            )

    async def _open_table(self):
        db = await self._connect()
        return await db.open_table(self.table_name)

    async def _drop_table(self) -> None:
        db = await self._connect()
        names = list((await db.list_tables()).tables)
        if self.table_name in names:
            await db.drop_table(self.table_name, ignore_missing=True)

    async def _ensure_indexes(self, table, *, force_rebuild: bool = False) -> None:
        if await table.count_rows() <= 0:
            return

        existing_indices = await table.list_indices()
        existing_names = {getattr(index, "name", None) for index in existing_indices}
        vector_params = dict(self.contract.vector_index_params)
        fts_params = dict(self.contract.fts_index_params)

        if force_rebuild or "vector_idx" not in existing_names:
            await table.create_index(
                "vector",
                replace=force_rebuild,
                config=IvfHnswSq(
                    distance_type=self.contract.distance_metric,
                    m=int(vector_params.get("m", 24)),
                    ef_construction=int(vector_params.get("ef_construction", 256)),
                    num_partitions=vector_params.get("num_partitions"),
                    max_iterations=int(vector_params.get("max_iterations", 50)),
                    sample_rate=int(vector_params.get("sample_rate", 256)),
                    target_partition_size=vector_params.get("target_partition_size"),
                ),
            )
        if force_rebuild or "text_idx" not in existing_names:
            await table.create_index(
                "text",
                replace=force_rebuild,
                config=FTS(
                    base_tokenizer=str(fts_params.get("base_tokenizer", "simple")),
                    language=str(fts_params.get("language", "English")),
                    max_token_length=int(fts_params.get("max_token_length", 40)),
                    lower_case=bool(fts_params.get("lower_case", True)),
                    stem=bool(fts_params.get("stem", True)),
                    remove_stop_words=bool(fts_params.get("remove_stop_words", True)),
                    ascii_folding=bool(fts_params.get("ascii_folding", True)),
                    ngram_min_length=int(fts_params.get("ngram_min_length", 3)),
                    ngram_max_length=int(fts_params.get("ngram_max_length", 3)),
                    prefix_only=bool(fts_params.get("prefix_only", False)),
                ),
            )
        for field in self.contract.filterable_fields:
            scalar_name = f"{field.name}_idx"
            if force_rebuild or scalar_name not in existing_names:
                await table.create_index(
                    field.name,
                    replace=force_rebuild,
                    config=BTree(),
                    name=scalar_name,
                )

    def _chunk_document(
        self, document: IndexDocument, *, skip_chunking: bool
    ) -> list[ChunkPiece]:
        metadata = document.metadata or {}
        prefix = ""
        prefix_value = metadata.get("prefix")
        if isinstance(prefix_value, str):
            prefix = prefix_value.strip()

        if skip_chunking:
            pieces = [chunk.strip() for chunk in document.chunks or []]
            return [
                ChunkPiece(
                    raw_text=piece,
                    indexed_text=f"{prefix}\n{piece}" if prefix else piece,
                )
                for piece in pieces
            ]
        chunker = RecursiveCharacterChunker(
            chunk_size=self.contract.chunk_size,
            chunk_overlap=self.contract.chunk_overlap,
        )
        raw_chunks = chunker.split_text(document.text or "")
        return [
            ChunkPiece(
                raw_text=raw,
                indexed_text=f"{prefix}\n{raw}" if prefix else raw,
            )
            for raw in raw_chunks
        ]

    def _build_rows(
        self,
        document: IndexDocument,
        chunks: list[ChunkPiece],
        vectors: list[list[float]],
    ) -> list[dict[str, Any]]:
        if len(vectors) != len(chunks):
            raise ValidationError("Embedding response size mismatch")

        attributes = document.attributes or {}
        rows: list[dict[str, Any]] = []
        for index, (piece, vector) in enumerate(
            zip(chunks, vectors, strict=True)
        ):
            if len(vector) != self.contract.embedding_dimensions_snapshot:
                raise ValidationError("Embedding dimensions mismatch")
            row: dict[str, Any] = {
                "chunk_id": f"{document.document_id}:{index}",
                "document_id": document.document_id,
                "chunk_index": index,
                "text": piece.indexed_text,
                "raw_text": piece.raw_text,
                "vector": [float(value) for value in vector],
                "metadata": serialize_metadata(document.metadata),
            }
            for field in self.contract.filterable_fields:
                row[field.name] = attributes.get(field.name)
            rows.append(row)
        return rows

    def _build_chunk_row(self, chunk: IndexChunk, vector: list[float]) -> dict[str, Any]:
        if len(vector) != self.contract.embedding_dimensions_snapshot:
            raise ValidationError("Embedding dimensions mismatch")
        row: dict[str, Any] = {
            "chunk_id": f"{chunk.document_id}:{chunk.chunk_index}",
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "text": chunk.indexed_text,
            "raw_text": chunk.raw_text,
            "vector": [float(value) for value in vector],
            "metadata": serialize_metadata(chunk.metadata),
        }
        for field in self.contract.filterable_fields:
            row[field.name] = (chunk.attributes or {}).get(field.name)
        return row


__all__ = [
    "LanceDBRetrievalEngine",
    "RetrievalQueryBuilder",
    "make_table_name",
]
