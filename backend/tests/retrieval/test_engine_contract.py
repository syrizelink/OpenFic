# -*- coding: utf-8 -*-
"""Test kontrak lintas adapter retrieval.

Skenario yang sama dijalankan terhadap setiap adapter yang memenuhi
``RetrievalEngine``. Tujuannya memastikan seam benar-benar nyata: pemanggil
seperti ``search_chapters`` boleh bergantung pada perilaku ini tanpa tahu adapter
mana yang aktif.

Adapter LanceDB dilewati otomatis bila pustaka native tidak dapat dimuat, misalnya
pada CPU tanpa dukungan x86-64-v2.
"""

from pathlib import Path
from typing import Any

import pytest

from app.retrieval.engine_protocol import (
    KEYWORD_ONLY_DIMENSIONS,
    KEYWORD_ONLY_EMBEDDING_REF_ID,
    RetrievalEngine,
)
from app.retrieval.types import (
    FilterableField,
    FilterableFieldType,
    IndexDocument,
    RetrievalIndexContract,
)


_EMBEDDING_DIMENSIONS = 8


def _filterable_fields() -> list[FilterableField]:
    return [
        FilterableField(name="project_id", field_type=FilterableFieldType.STRING),
        FilterableField(name="chapter_id", field_type=FilterableFieldType.STRING),
        FilterableField(name="volume_id", field_type=FilterableFieldType.STRING),
    ]


class _StubEmbeddingConfig:
    """Konfigurasi tiruan agar validasi kontrak LanceDB terlewati."""

    def __init__(self, model_id: str, dimensions: int) -> None:
        self.model_id = model_id
        self.dimensions = dimensions


class _StubEmbeddingClient:
    """Klien embedding deterministik berbasis kantong kata sederhana.

    Tidak memanggil jaringan. Vektor dibentuk dari hash token sehingga teks yang
    memuat kata yang sama menghasilkan arah vektor yang mirip.
    """

    def __init__(self, dimensions: int = _EMBEDDING_DIMENSIONS) -> None:
        self.config = _StubEmbeddingConfig("stub-embedding", dimensions)
        self._dimensions = dimensions

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for token in (text or "").lower().split():
            vector[hash(token) % self._dimensions] += 1.0
        if not any(vector):
            vector[0] = 1.0
        return vector

    async def embed(self, texts: list[str]) -> Any:
        class _Response:
            def __init__(self, embeddings: list[list[float]]) -> None:
                self.embeddings = embeddings

        return _Response([self._vector(text) for text in texts])

    async def embed_single(self, text: str) -> list[float]:
        return self._vector(text)


def _keyword_only_engine(tmp_path: Path) -> tuple[RetrievalEngine, Any]:
    from app.retrieval.engine_sqlite_fts import SqliteFtsRetrievalEngine

    contract = RetrievalIndexContract(
        embedding_model_ref_id=KEYWORD_ONLY_EMBEDDING_REF_ID,
        embedding_model_id_snapshot=KEYWORD_ONLY_EMBEDDING_REF_ID,
        embedding_dimensions_snapshot=KEYWORD_ONLY_DIMENSIONS,
        chunk_size=400,
        chunk_overlap=40,
        filterable_fields=_filterable_fields(),
    )
    engine = SqliteFtsRetrievalEngine(
        base_dir=tmp_path,
        table_name="idx_contract",
        contract=contract,
    )
    return engine, None


def _lancedb_engine(tmp_path: Path) -> tuple[RetrievalEngine, Any]:
    lancedb_engine_module = pytest.importorskip(
        "app.retrieval.engine",
        reason="LanceDB tidak dapat dimuat pada CPU ini",
    )
    contract = RetrievalIndexContract(
        embedding_model_ref_id="stub-ref",
        embedding_model_id_snapshot="stub-embedding",
        embedding_dimensions_snapshot=_EMBEDDING_DIMENSIONS,
        chunk_size=400,
        chunk_overlap=40,
        filterable_fields=_filterable_fields(),
    )
    engine = lancedb_engine_module.LanceDBRetrievalEngine(
        base_dir=tmp_path,
        table_name="idx_contract",
        contract=contract,
    )
    return engine, _StubEmbeddingClient()


ADAPTERS = [
    pytest.param(_keyword_only_engine, id="sqlite_fts"),
    pytest.param(_lancedb_engine, id="lancedb"),
]


def _document(doc_id: str, text: str, project_id: str = "p1") -> IndexDocument:
    return IndexDocument(
        document_id=doc_id,
        text=text,
        attributes={
            "project_id": project_id,
            "chapter_id": doc_id,
            "volume_id": "v1",
        },
        metadata={"prefix": f"Bab {doc_id}"},
    )


@pytest.mark.parametrize("make_engine", ADAPTERS)
def test_adapter_satisfies_protocol(make_engine, tmp_path: Path) -> None:
    engine, _client = make_engine(tmp_path)

    assert isinstance(engine, RetrievalEngine)
    assert engine.contract.chunk_size == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("make_engine", ADAPTERS)
async def test_index_then_bm25_query_finds_document(
    make_engine, tmp_path: Path
) -> None:
    engine, client = make_engine(tmp_path)
    await engine.index_documents(
        [_document("ch1", "Aruna menggenggam pedang cahaya di puncak menara.")],
        client,
    )
    await engine.finalize_chunk_index()

    hits = await engine.query("pedang cahaya", client).bm25().limit(5).run()

    assert [hit.document_id for hit in hits] == ["ch1"]
    assert hits[0].text.startswith("Aruna menggenggam")


@pytest.mark.asyncio
@pytest.mark.parametrize("make_engine", ADAPTERS)
async def test_filter_eq_scopes_results_by_project(make_engine, tmp_path: Path) -> None:
    engine, client = make_engine(tmp_path)
    await engine.index_documents(
        [
            _document("ch1", "Pedang cahaya milik Aruna.", project_id="p1"),
            _document("ch2", "Pedang cahaya di gudang lain.", project_id="p2"),
        ],
        client,
    )
    await engine.finalize_chunk_index()

    hits = (
        await engine.query("pedang cahaya", client)
        .bm25()
        .filter_eq("project_id", "p1")
        .limit(5)
        .run()
    )

    assert [hit.document_id for hit in hits] == ["ch1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("make_engine", ADAPTERS)
async def test_delete_document_removes_it(make_engine, tmp_path: Path) -> None:
    engine, client = make_engine(tmp_path)
    await engine.index_documents(
        [
            _document("ch1", "Pedang cahaya milik Aruna."),
            _document("ch2", "Aruna berjalan pulang sendiri."),
        ],
        client,
    )
    await engine.finalize_chunk_index()

    await engine.delete_document("ch1")

    hits = await engine.query("pedang", client).bm25().limit(5).run()
    assert "ch1" not in [hit.document_id for hit in hits]


@pytest.mark.asyncio
@pytest.mark.parametrize("make_engine", ADAPTERS)
async def test_scores_stay_within_confidence_range(make_engine, tmp_path: Path) -> None:
    engine, client = make_engine(tmp_path)
    await engine.index_documents([_document("ch1", "pedang cahaya berkilau")], client)
    await engine.finalize_chunk_index()

    hits = await engine.query("pedang", client).bm25().limit(5).run()

    assert hits
    for hit in hits:
        assert 0.0 <= hit.score <= 1.0
        assert hit.matched_by in {"bm25", "vector", "hybrid"}


@pytest.mark.asyncio
@pytest.mark.parametrize("make_engine", ADAPTERS)
async def test_rebuild_replaces_all_content(make_engine, tmp_path: Path) -> None:
    engine, client = make_engine(tmp_path)
    await engine.index_documents([_document("ch1", "pedang lama")], client)
    await engine.finalize_chunk_index()

    await engine.rebuild([_document("ch2", "tombak baru")], client)
    await engine.finalize_chunk_index()

    hits = await engine.query("tombak", client).bm25().limit(5).run()
    assert [hit.document_id for hit in hits] == ["ch2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("make_engine", ADAPTERS)
async def test_drop_table_discards_indexed_content(make_engine, tmp_path: Path) -> None:
    """Setelah drop, isi indeks tidak boleh lagi dapat dikembalikan.

    Perilaku tepatnya berbeda antaradapter dan itu memang di luar kontrak:
    SQLite FTS5 mengembalikan daftar kosong, sedangkan LanceDB melempar galat
    karena tabelnya sudah tidak ada. Pemanggil produksi tidak pernah menyentuh
    jalur ini karena ``OpenFicRetrievalService.query`` lebih dulu menolak indeks
    yang statusnya bukan ``ready``. Yang dijamin kontrak hanyalah: tidak ada
    dokumen lama yang bisa terbaca lagi.
    """
    engine, client = make_engine(tmp_path)
    await engine.index_documents([_document("ch1", "pedang")], client)
    await engine.finalize_chunk_index()

    await engine.drop_table()

    try:
        hits = await engine.query("pedang", client).bm25().limit(5).run()
    except Exception:
        # Penyimpanan sudah hilang seluruhnya: itu pun memenuhi kontrak.
        return
    assert hits == []
