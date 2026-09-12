# -*- coding: utf-8 -*-
"""Adapter retrieval berbasis SQLite FTS5.

Adapter ini menyediakan pencarian kata kunci BM25 tanpa dependensi native apa
pun, sehingga dapat berjalan di CPU yang tidak mendukung x86-64-v2 (AVX/SSE4.2).
Dipakai pada deployment ``OPENFIC_CLOUD_ONLY=true`` di mana LanceDB dan NumPy
tidak dapat diimpor.

Batas yang disengaja:

* Tidak ada pencarian vektor atau semantik. Hanya kecocokan leksikal.
* ``embedding_client`` diterima demi kesesuaian interface, tetapi diabaikan.

Setiap indeks disimpan pada berkas SQLite tersendiri di bawah ``base_dir``,
terpisah dari ``openfic.db``, supaya indeks dapat dibuang dan dibangun ulang
tanpa menyentuh data karya.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from app.retrieval.internal.common.codec import serialize_metadata
from app.retrieval.internal.indexing.chunking import ChunkPiece, chunk_document
from app.retrieval.internal.query.sqlite_fts_builder import (
    FilterPredicate,
    SqliteFtsQueryBuilder,
)
from app.retrieval.internal.validation import validate_batch
from app.retrieval.types import (
    BatchIndexResult,
    ChunkIndexResult,
    DocumentIndexFailure,
    DocumentIndexSuccess,
    FilterableFieldType,
    IndexChunk,
    IndexDocument,
    RetrievalIndexContract,
)


# Kolom tetap pada tabel konten. Kolom filterable ditambahkan secara dinamis
# mengikuti kontrak.
_FIXED_COLUMNS = (
    "chunk_id",
    "document_id",
    "chunk_index",
    "text",
    "raw_text",
    "metadata",
)


def _quote_identifier(name: str) -> str:
    """Mengutip pengenal SQL memakai tanda kutip ganda.

    Nama tabel berasal dari ``make_table_name`` (hex sha1) dan nama kolom berasal
    dari ``contract.filterable_fields`` yang sudah divalidasi, tetapi pengutipan
    tetap diterapkan sebagai lapisan pertahanan kedua.
    """
    if '"' in name:
        raise ValueError(f"Nama pengenal tidak sah: {name}")
    return f'"{name}"'


class SqliteFtsRetrievalEngine:
    """Adapter retrieval BM25 di atas SQLite FTS5."""

    def __init__(
        self,
        *,
        base_dir: Path,
        table_name: str,
        contract: RetrievalIndexContract,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.table_name = table_name
        self._contract = contract

    @property
    def contract(self) -> RetrievalIndexContract:
        return self._contract

    @property
    def db_path(self) -> Path:
        return self.base_dir / f"{self.table_name}.sqlite3"

    @property
    def _content_table(self) -> str:
        return self.table_name

    @property
    def _fts_table(self) -> str:
        return f"{self.table_name}_fts"

    @property
    def _filterable_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self._contract.filterable_fields)

    # ------------------------------------------------------------------
    # Akses SQLite. Semua operasi blocking dijalankan di thread pool supaya
    # event loop tidak tertahan.
    # ------------------------------------------------------------------

    def _connect_sync(self) -> sqlite3.Connection:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    async def _run(self, function: Callable[[sqlite3.Connection], Any]) -> Any:
        def _execute() -> Any:
            connection = self._connect_sync()
            try:
                result = function(connection)
                connection.commit()
                return result
            finally:
                connection.close()

        return await asyncio.to_thread(_execute)

    def _ensure_schema_sync(self, connection: sqlite3.Connection) -> None:
        content = _quote_identifier(self._content_table)
        fts = _quote_identifier(self._fts_table)

        columns = [
            "chunk_id TEXT PRIMARY KEY",
            "document_id TEXT NOT NULL",
            "chunk_index INTEGER NOT NULL",
            "text TEXT NOT NULL",
            "raw_text TEXT NOT NULL",
            "metadata TEXT NOT NULL",
        ]
        # Kolom filterable disimpan sebagai TEXT/INTEGER/REAL sesuai kontrak;
        # SQLite bertipe dinamis sehingga TEXT aman untuk semua nilai skalar.
        columns.extend(
            f"{_quote_identifier(name)} TEXT" for name in self._filterable_names
        )
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {content} ({', '.join(columns)})"
        )
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS "
            f"{_quote_identifier(self._content_table + '_doc_idx')} "
            f"ON {content} (document_id)"
        )
        # Tabel FTS5 menyimpan salinan teks terindeks dan ditautkan ke tabel
        # konten melalui rowid. Tabel contentless (``content=''``) sengaja tidak
        # dipakai karena tidak mendukung DELETE biasa, sementara adapter ini
        # perlu membuang chunk per dokumen saat bab disunting.
        connection.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {fts} "
            f"USING fts5(text, tokenize='unicode61 remove_diacritics 2')"
        )

    async def _ensure_schema(self) -> None:
        await self._run(self._ensure_schema_sync)

    # ------------------------------------------------------------------
    # Penulisan chunk
    # ------------------------------------------------------------------

    def _insert_pieces_sync(
        self,
        connection: sqlite3.Connection,
        rows: list[dict[str, Any]],
        *,
        replace_document_ids: set[str] | None,
    ) -> int:
        self._ensure_schema_sync(connection)
        if replace_document_ids:
            self._delete_documents_sync(connection, list(replace_document_ids))

        content = _quote_identifier(self._content_table)
        fts = _quote_identifier(self._fts_table)
        column_names = [*_FIXED_COLUMNS, *self._filterable_names]
        placeholders = ", ".join("?" for _ in column_names)
        quoted_columns = ", ".join(_quote_identifier(name) for name in column_names)

        inserted = 0
        for row in rows:
            cursor = connection.execute(
                f"INSERT OR REPLACE INTO {content} ({quoted_columns}) "
                f"VALUES ({placeholders})",
                [row.get(name) for name in column_names],
            )
            rowid = cursor.lastrowid
            # Jaga agar baris FTS lama untuk rowid yang sama tidak menumpuk saat
            # INSERT OR REPLACE menimpa chunk_id yang sudah ada.
            connection.execute(f"DELETE FROM {fts} WHERE rowid = ?", (rowid,))
            connection.execute(
                f"INSERT INTO {fts} (rowid, text) VALUES (?, ?)",
                (rowid, row["text"]),
            )
            inserted += 1
        return inserted

    def _build_row(self, chunk: IndexChunk) -> dict[str, Any]:
        row: dict[str, Any] = {
            "chunk_id": f"{chunk.document_id}:{chunk.chunk_index}",
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "text": chunk.indexed_text,
            "raw_text": chunk.raw_text,
            "metadata": serialize_metadata(chunk.metadata),
        }
        attributes = chunk.attributes or {}
        for name in self._filterable_names:
            value = attributes.get(name)
            row[name] = None if value is None else str(value)
        return row

    def _build_document_rows(
        self,
        document: IndexDocument,
        pieces: list[ChunkPiece],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, piece in enumerate(pieces):
            chunk = IndexChunk(
                document_id=document.document_id,
                chunk_index=index,
                raw_text=piece.raw_text,
                indexed_text=piece.indexed_text,
                attributes=document.attributes,
                metadata=document.metadata,
            )
            rows.append(self._build_row(chunk))
        return rows

    async def index_chunks(
        self,
        chunks: list[IndexChunk],
        embedding_client: Any = None,
        *,
        replace_document_ids: set[str] | None = None,
    ) -> ChunkIndexResult:
        """Menambahkan batch chunk. ``embedding_client`` diabaikan."""
        del embedding_client
        if not chunks:
            return ChunkIndexResult(succeeded_chunk_count=0)
        rows = [self._build_row(chunk) for chunk in chunks]
        inserted = await self._run(
            lambda connection: self._insert_pieces_sync(
                connection, rows, replace_document_ids=replace_document_ids
            )
        )
        return ChunkIndexResult(succeeded_chunk_count=int(inserted))

    async def finalize_chunk_index(self) -> None:
        """Mengoptimalkan indeks FTS5 setelah seluruh batch selesai ditulis."""
        fts = _quote_identifier(self._fts_table)

        def _optimize(connection: sqlite3.Connection) -> None:
            self._ensure_schema_sync(connection)
            connection.execute(f"INSERT INTO {fts} ({fts}) VALUES ('optimize')")

        await self._run(_optimize)

    # ------------------------------------------------------------------
    # Penghapusan
    # ------------------------------------------------------------------

    def _delete_documents_sync(
        self, connection: sqlite3.Connection, document_ids: list[str]
    ) -> None:
        if not document_ids:
            return
        content = _quote_identifier(self._content_table)
        fts = _quote_identifier(self._fts_table)
        unique_ids = list(dict.fromkeys(document_ids))
        placeholders = ", ".join("?" for _ in unique_ids)
        # Baris FTS dibuang lebih dulu karena penentuan rowid-nya bergantung pada
        # baris tabel konten yang masih ada.
        connection.execute(
            f"DELETE FROM {fts} WHERE rowid IN "
            f"(SELECT rowid FROM {content} WHERE document_id IN ({placeholders}))",
            unique_ids,
        )
        connection.execute(
            f"DELETE FROM {content} WHERE document_id IN ({placeholders})",
            unique_ids,
        )

    async def delete_document(self, document_id: str) -> None:
        await self.delete_documents([document_id])

    async def delete_documents(self, document_ids: list[str]) -> None:
        if not document_ids:
            return
        if not self.db_path.exists():
            return
        await self._run(
            lambda connection: self._delete_documents_sync(connection, document_ids)
        )

    async def drop_table(self) -> None:
        """Membuang seluruh berkas indeks. Data karya tidak tersentuh karena
        indeks disimpan pada berkas SQLite terpisah."""

        def _drop() -> None:
            for suffix in ("", "-wal", "-shm"):
                path = Path(str(self.db_path) + suffix)
                path.unlink(missing_ok=True)

        await asyncio.to_thread(_drop)

    # ------------------------------------------------------------------
    # Pengindeksan batch dokumen
    # ------------------------------------------------------------------

    async def index_documents(
        self,
        documents: list[IndexDocument],
        embedding_client: Any = None,
        *,
        skip_chunking: bool = False,
        max_consecutive_failures: int = 5,
        on_status_change: Callable[[str, str | None], Any] | None = None,
    ) -> BatchIndexResult:
        del embedding_client
        validate_batch(self._contract, documents, skip_chunking=skip_chunking)
        await self._notify(on_status_change, "building", None)
        await self._ensure_schema()

        successes: list[DocumentIndexSuccess] = []
        failures: list[DocumentIndexFailure] = []
        consecutive_failures = 0
        stopped_early = False
        stop_reason: str | None = None

        for document in documents:
            try:
                pieces = chunk_document(
                    document.text,
                    document.chunks,
                    dict(document.metadata or {}),
                    chunk_size=self._contract.chunk_size,
                    chunk_overlap=self._contract.chunk_overlap,
                    skip_chunking=skip_chunking,
                )
                if not pieces:
                    raise ValueError("Document produced no chunks")
                rows = self._build_document_rows(document, pieces)
                await self._run(
                    lambda connection, rows=rows, doc=document: (
                        self._insert_pieces_sync(
                            connection,
                            rows,
                            replace_document_ids={doc.document_id},
                        )
                    )
                )
                successes.append(
                    DocumentIndexSuccess(
                        document_id=document.document_id,
                        chunk_count=len(rows),
                    )
                )
                consecutive_failures = 0
            except Exception as exc:
                logger.warning(
                    "Retrieval FTS5: gagal mengindeks dokumen {}: {}",
                    document.document_id,
                    exc,
                )
                failures.append(
                    DocumentIndexFailure(
                        document_id=document.document_id,
                        error=str(exc),
                    )
                )
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    stopped_early = True
                    stop_reason = (
                        f"{consecutive_failures} kegagalan berurutan saat mengindeks"
                    )
                    break

        if successes:
            await self.finalize_chunk_index()

        status = "ready" if not failures else "ready" if successes else "error"
        await self._notify(
            on_status_change,
            status,
            stop_reason if status == "error" else None,
        )
        return BatchIndexResult(
            total_documents=len(documents),
            succeeded_count=len(successes),
            failed_count=len(failures),
            stopped_early=stopped_early,
            stop_reason=stop_reason,
            succeeded=successes,
            failed=failures,
        )

    async def rebuild(
        self,
        documents: list[IndexDocument],
        embedding_client: Any = None,
        *,
        skip_chunking: bool = False,
        max_consecutive_failures: int = 5,
        on_status_change: Callable[[str, str | None], Any] | None = None,
    ) -> BatchIndexResult:
        validate_batch(self._contract, documents, skip_chunking=skip_chunking)
        await self.drop_table()
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
        """Membangun ulang indeks FTS5 tanpa mengubah data chunk."""
        await self._notify(on_status_change, "building", None)
        fts = _quote_identifier(self._fts_table)

        def _rebuild(connection: sqlite3.Connection) -> None:
            self._ensure_schema_sync(connection)
            connection.execute(f"INSERT INTO {fts} ({fts}) VALUES ('rebuild')")

        await self._run(_rebuild)
        await self._notify(on_status_change, "ready", None)

    # ------------------------------------------------------------------
    # Kueri
    # ------------------------------------------------------------------

    def query(self, text: str, embedding_client: Any = None) -> SqliteFtsQueryBuilder:
        """Mengembalikan pembangun kueri BM25 yang belum dieksekusi."""
        del embedding_client
        return SqliteFtsQueryBuilder(engine=self, query_text=text)

    def _render_predicate(
        self, predicate: FilterPredicate
    ) -> tuple[str, list[Any]]:
        """Menerjemahkan satu predikat menjadi klausa SQL berparameter.

        Semua kolom filterable disimpan sebagai TEXT, jadi pembanding rentang
        pada kolom numerik harus di-CAST lebih dulu. Tanpa CAST, SQLite akan
        membandingkan secara leksikografis sehingga "10" dianggap lebih kecil
        daripada "9".
        """
        field = next(
            (
                item
                for item in self._contract.filterable_fields
                if item.name == predicate.field
            ),
            None,
        )
        if field is None:
            raise ValueError(f"Undeclared filterable field: {predicate.field}")

        numeric = field.field_type in (
            FilterableFieldType.INTEGER,
            FilterableFieldType.FLOAT,
        )
        column = f"c.{_quote_identifier(predicate.field)}"
        expression = f"CAST({column} AS REAL)" if numeric else column

        def _bind(value: Any) -> Any:
            if value is None:
                return None
            if numeric:
                return float(value)
            if isinstance(value, bool):
                return str(value)
            return str(value)

        if predicate.operator == "eq":
            value = predicate.values[0]
            if value is None:
                return f"{column} IS NULL", []
            return f"{expression} = ?", [_bind(value)]

        if predicate.operator == "in":
            placeholders = ", ".join("?" for _ in predicate.values)
            return (
                f"{expression} IN ({placeholders})",
                [_bind(value) for value in predicate.values],
            )

        if predicate.operator == "gte":
            return f"{expression} >= ?", [_bind(predicate.values[0])]

        if predicate.operator == "lte":
            return f"{expression} <= ?", [_bind(predicate.values[0])]

        raise ValueError(f"Unsupported filter operator: {predicate.operator}")

    async def match_rows(
        self,
        match_expression: str,
        *,
        filters: tuple[FilterPredicate, ...] = (),
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Menjalankan satu kueri MATCH dan mengembalikan baris mentah.

        Nilai ``bm25()`` disertakan pada kunci ``_bm25_raw`` agar pemanggil dapat
        menormalisasinya menjadi tingkat keyakinan.
        """
        if not self.db_path.exists():
            return []

        content = _quote_identifier(self._content_table)
        fts = _quote_identifier(self._fts_table)

        where_parts = [f"{fts} MATCH ?"]
        parameters: list[Any] = [match_expression]
        for predicate in filters:
            clause, values = self._render_predicate(predicate)
            where_parts.append(clause)
            parameters.extend(values)
        parameters.append(int(limit))

        statement = (
            f"SELECT c.chunk_id AS chunk_id, c.document_id AS document_id, "
            f"c.chunk_index AS chunk_index, c.text AS text, "
            f"c.raw_text AS raw_text, c.metadata AS metadata, "
            f"bm25({fts}) AS _bm25_raw "
            f"FROM {fts} JOIN {content} AS c ON c.rowid = {fts}.rowid "
            f"WHERE {' AND '.join(where_parts)} "
            f"ORDER BY bm25({fts}) LIMIT ?"
        )

        def _select(connection: sqlite3.Connection) -> list[dict[str, Any]]:
            try:
                cursor = connection.execute(statement, parameters)
            except sqlite3.OperationalError as exc:
                # Tabel belum terbentuk atau ekspresi MATCH ditolak: perlakukan
                # sebagai hasil kosong, bukan kegagalan keras.
                logger.info("Retrieval FTS5: kueri tidak dapat dijalankan: {}", exc)
                return []
            return [dict(row) for row in cursor.fetchall()]

        return await self._run(_select)

    # ------------------------------------------------------------------
    # Utilitas
    # ------------------------------------------------------------------

    async def count_chunks(self) -> int:
        """Menghitung jumlah chunk terindeks. Dipakai pengujian dan diagnostik."""
        if not self.db_path.exists():
            return 0
        content = _quote_identifier(self._content_table)

        def _count(connection: sqlite3.Connection) -> int:
            try:
                row = connection.execute(f"SELECT count(*) FROM {content}").fetchone()
            except sqlite3.OperationalError:
                return 0
            return int(row[0]) if row else 0

        return await self._run(_count)

    @staticmethod
    async def _notify(
        on_status_change: Callable[[str, str | None], Any] | None,
        status: str,
        error: str | None,
    ) -> None:
        if on_status_change is None:
            return
        maybe_awaitable = on_status_change(status, error)
        if asyncio.iscoroutine(maybe_awaitable):
            await maybe_awaitable


__all__ = ["SqliteFtsRetrievalEngine"]
