# -*- coding: utf-8 -*-
"""Seam definition for retrieval engines.

Modul ini sengaja bebas dari dependensi native (LanceDB, NumPy, PyArrow) supaya
dapat diimpor di lingkungan CPU tanpa AVX/SSE4.2. Adapter konkret yang memuat
pustaka native harus diimpor di dalam fungsi, bukan pada tingkat modul.

Dua adapter memenuhi interface ini:

* ``LanceDBRetrievalEngine`` (``app.retrieval.engine``) - pencarian hibrida
  vektor + BM25, membutuhkan CPU dengan dukungan x86-64-v2.
* ``SqliteFtsRetrievalEngine`` (``app.retrieval.engine_sqlite_fts``) - pencarian
  kata kunci BM25 melalui SQLite FTS5, murni Python.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from app.retrieval.types import (
    BatchIndexResult,
    ChunkIndexResult,
    IndexChunk,
    IndexDocument,
    RetrievalIndexContract,
)


#: Nilai ``embedding_model_ref_id`` yang menandai kontrak tanpa embedding.
#: Dipakai adapter FTS5 supaya validasi kontrak tidak menuntut model embedding.
KEYWORD_ONLY_EMBEDDING_REF_ID = "__keyword_only__"

#: Dimensi vektor tiruan untuk kontrak keyword-only. ``RetrievalIndexContract``
#: mensyaratkan ``embedding_dimensions_snapshot >= 1``, jadi nilai ini dipakai
#: sebagai sentinel yang tidak pernah benar-benar dipakai untuk menyimpan vektor.
KEYWORD_ONLY_DIMENSIONS = 1


def is_keyword_only_contract(contract: RetrievalIndexContract) -> bool:
    """Menentukan apakah kontrak berjalan tanpa embedding sama sekali."""
    return contract.embedding_model_ref_id == KEYWORD_ONLY_EMBEDDING_REF_ID


def is_keyword_only_model_ref(model_ref_id: str | None) -> bool:
    """Menentukan apakah rujukan model menunjuk model embedding tiruan."""
    return model_ref_id == KEYWORD_ONLY_EMBEDDING_REF_ID


@runtime_checkable
class RetrievalEngine(Protocol):
    """Interface yang harus dipenuhi setiap adapter retrieval.

    Kontrak perilaku yang tidak terlihat dari tanda tangan tipe:

    * ``contract`` bersifat hanya-baca dan tidak berubah selama masa hidup
      instance.
    * ``index_chunks`` menambahkan chunk tanpa membangun ulang indeks
      pencarian; pemanggil wajib menutup rangkaian dengan
      ``finalize_chunk_index`` supaya indeks siap dipakai.
    * ``query`` mengembalikan pembangun kueri yang belum dieksekusi; eksekusi
      terjadi saat ``run()`` dipanggil pada pembangun tersebut.
    * ``on_status_change`` menerima ``(status, error)`` dan boleh berupa fungsi
      sinkron maupun coroutine.
    """

    @property
    def contract(self) -> RetrievalIndexContract:
        """Kontrak indeks yang sedang dipakai adapter ini."""
        ...

    async def index_documents(
        self,
        documents: list[IndexDocument],
        embedding_client: Any,
        *,
        skip_chunking: bool = False,
        max_consecutive_failures: int = 5,
        on_status_change: Callable[[str, str | None], Any] | None = None,
    ) -> BatchIndexResult:
        """Memotong, lalu mengindeks sekumpulan dokumen secara batch."""
        ...

    async def index_chunks(
        self,
        chunks: list[IndexChunk],
        embedding_client: Any,
        *,
        replace_document_ids: set[str] | None = None,
    ) -> ChunkIndexResult:
        """Menambahkan satu batch chunk yang sudah dipotong sebelumnya."""
        ...

    async def finalize_chunk_index(self) -> None:
        """Membangun indeks pencarian setelah seluruh batch chunk ditulis."""
        ...

    async def delete_document(self, document_id: str) -> None:
        """Menghapus seluruh chunk milik satu dokumen."""
        ...

    async def delete_documents(self, document_ids: list[str]) -> None:
        """Menghapus seluruh chunk milik beberapa dokumen."""
        ...

    async def rebuild(
        self,
        documents: list[IndexDocument],
        embedding_client: Any,
        *,
        skip_chunking: bool = False,
        max_consecutive_failures: int = 5,
        on_status_change: Callable[[str, str | None], Any] | None = None,
    ) -> BatchIndexResult:
        """Mengosongkan penyimpanan lalu mengindeks ulang dari awal."""
        ...

    async def rebuild_indexes(
        self,
        *,
        on_status_change: Callable[[str, str | None], Any] | None = None,
    ) -> None:
        """Membangun ulang indeks pencarian tanpa mengubah data chunk."""
        ...

    async def drop_table(self) -> None:
        """Membuang tabel/penyimpanan indeks bila ada."""
        ...

    def query(self, text: str, embedding_client: Any) -> Any:
        """Mengembalikan pembangun kueri yang belum dieksekusi.

        Tipe kembalian sengaja ``Any``: setiap adapter punya pembangun kueri
        sendiri (``RetrievalQueryBuilder`` untuk LanceDB, ``SqliteFtsQueryBuilder``
        untuk FTS5) yang menyediakan rantai metode setara.
        """
        ...


__all__ = [
    "KEYWORD_ONLY_DIMENSIONS",
    "KEYWORD_ONLY_EMBEDDING_REF_ID",
    "RetrievalEngine",
    "is_keyword_only_contract",
]
