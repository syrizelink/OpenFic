# -*- coding: utf-8 -*-
"""Unit test adapter SQLite FTS5."""

from pathlib import Path

import pytest

from app.retrieval.engine_protocol import (
    KEYWORD_ONLY_DIMENSIONS,
    KEYWORD_ONLY_EMBEDDING_REF_ID,
    RetrievalEngine,
    is_keyword_only_contract,
    is_keyword_only_model_ref,
)
from app.retrieval.engine_sqlite_fts import SqliteFtsRetrievalEngine
from app.retrieval.internal.query.sqlite_fts_builder import (
    build_match_expression,
    extract_match_tokens,
    normalize_bm25_scores,
)
from app.retrieval.types import (
    FilterableField,
    FilterableFieldType,
    IndexChunk,
    IndexDocument,
    RetrievalIndexContract,
)


def _contract(chunk_size: int = 400) -> RetrievalIndexContract:
    return RetrievalIndexContract(
        embedding_model_ref_id=KEYWORD_ONLY_EMBEDDING_REF_ID,
        embedding_model_id_snapshot=KEYWORD_ONLY_EMBEDDING_REF_ID,
        embedding_dimensions_snapshot=KEYWORD_ONLY_DIMENSIONS,
        chunk_size=chunk_size,
        chunk_overlap=40,
        filterable_fields=[
            FilterableField(name="project_id", field_type=FilterableFieldType.STRING),
            FilterableField(name="chapter_id", field_type=FilterableFieldType.STRING),
            FilterableField(name="volume_id", field_type=FilterableFieldType.STRING),
        ],
    )


def _engine(tmp_path: Path, **kwargs) -> SqliteFtsRetrievalEngine:
    return SqliteFtsRetrievalEngine(
        base_dir=tmp_path,
        table_name="idx_unit",
        contract=_contract(**kwargs),
    )


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


# ---------------------------------------------------------------------------
# Helper tokenisasi dan skor
# ---------------------------------------------------------------------------


def test_extract_match_tokens_strips_fts5_operators() -> None:
    tokens = extract_match_tokens('pedang* AND "cahaya" NEAR(x) ^start col:val -neg')

    assert '"' not in "".join(tokens)
    assert "*" not in "".join(tokens)
    assert ":" not in "".join(tokens)
    assert "pedang" in tokens
    assert "cahaya" in tokens


def test_extract_match_tokens_deduplicates_and_lowercases() -> None:
    assert extract_match_tokens("Pedang pedang PEDANG") == ["pedang"]


def test_extract_match_tokens_handles_empty_and_punctuation_only() -> None:
    assert extract_match_tokens("") == []
    assert extract_match_tokens("   ") == []
    assert extract_match_tokens("!!! ??? ...") == []


def test_extract_match_tokens_supports_cjk_and_accents() -> None:
    tokens = extract_match_tokens("café 剑客 カタカナ")

    assert any("caf" in token for token in tokens)
    assert any("\u5251" in token for token in tokens)


def test_build_match_expression_quotes_every_token() -> None:
    assert build_match_expression(["a", "b"], operator="AND") == '"a" AND "b"'
    assert build_match_expression(["a", "b"], operator="OR") == '"a" OR "b"'
    assert build_match_expression([], operator="AND") is None


def test_build_match_expression_rejects_unknown_operator() -> None:
    with pytest.raises(ValueError):
        build_match_expression(["a"], operator="NOT")


def test_normalize_bm25_scores_maps_best_match_to_one() -> None:
    scores = normalize_bm25_scores([-5.0, -2.5, -1.0])

    assert scores[0] == pytest.approx(1.0)
    assert scores[1] == pytest.approx(0.5)
    assert all(0.0 <= score <= 1.0 for score in scores)


def test_normalize_bm25_scores_handles_empty_and_zero() -> None:
    assert normalize_bm25_scores([]) == []
    assert normalize_bm25_scores([0.0, 0.0]) == [1.0, 1.0]


# ---------------------------------------------------------------------------
# Kontrak keyword-only
# ---------------------------------------------------------------------------


def test_keyword_only_contract_detection() -> None:
    assert is_keyword_only_contract(_contract()) is True
    assert is_keyword_only_model_ref(KEYWORD_ONLY_EMBEDDING_REF_ID) is True
    assert is_keyword_only_model_ref("some-real-model") is False
    assert is_keyword_only_model_ref(None) is False


def test_engine_satisfies_retrieval_engine_protocol(tmp_path: Path) -> None:
    assert isinstance(_engine(tmp_path), RetrievalEngine)


# ---------------------------------------------------------------------------
# Pengindeksan dan kueri
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_documents_then_query_returns_hit(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    result = await engine.index_documents(
        [_document("ch1", "Aruna menggenggam pedang cahaya di puncak menara.")]
    )

    assert result.succeeded_count == 1
    assert result.failed_count == 0
    assert await engine.count_chunks() == 1

    hits = await engine.query("pedang cahaya").run()

    assert [hit.document_id for hit in hits] == ["ch1"]
    assert hits[0].matched_by == "bm25"
    assert hits[0].bm25_score is not None
    assert hits[0].vector_score is None
    assert 0.0 <= hits[0].score <= 1.0


@pytest.mark.asyncio
async def test_query_returns_raw_text_without_prefix(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents([_document("ch1", "Pedang itu berkilau.")])

    hits = await engine.query("pedang").run()

    assert hits[0].text == "Pedang itu berkilau."


@pytest.mark.asyncio
async def test_filter_eq_isolates_projects(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents(
        [
            _document("ch1", "Pedang cahaya milik Aruna.", project_id="p1"),
            _document("ch2", "Pedang cahaya di gudang lain.", project_id="p2"),
        ]
    )

    hits = await engine.query("pedang cahaya").filter_eq("project_id", "p1").run()

    assert [hit.document_id for hit in hits] == ["ch1"]


@pytest.mark.asyncio
async def test_query_falls_back_from_and_to_or(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents([_document("ch1", "Hanya menyebut pedang saja.")])

    # "naga" tidak ada di dokumen, jadi AND gagal dan OR mengambil alih.
    hits = await engine.query("pedang naga").run()

    assert [hit.document_id for hit in hits] == ["ch1"]


@pytest.mark.asyncio
async def test_query_with_no_searchable_tokens_returns_empty(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents([_document("ch1", "Isi bab.")])

    assert await engine.query("!!! ???").run() == []


@pytest.mark.asyncio
async def test_query_on_missing_index_returns_empty(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    assert await engine.query("apa pun").run() == []
    assert await engine.count_chunks() == 0


@pytest.mark.asyncio
async def test_limit_caps_result_count(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents(
        [_document(f"ch{index}", "pedang cahaya") for index in range(5)]
    )

    hits = await engine.query("pedang").limit(2).run()

    assert len(hits) == 2


@pytest.mark.asyncio
async def test_vector_mode_is_rejected(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with pytest.raises(ValueError, match="tidak mendukung pencarian vektor"):
        engine.query("pedang").vector()


@pytest.mark.asyncio
async def test_vector_params_are_accepted_but_ignored(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents([_document("ch1", "pedang cahaya")])

    hits = (
        await engine.query("pedang")
        .hybrid()
        .vector_top_k(40)
        .bm25_top_k(40)
        .ef(200)
        .rrf(k=60)
        .run()
    )

    assert [hit.document_id for hit in hits] == ["ch1"]


@pytest.mark.asyncio
async def test_undeclared_filter_field_is_rejected(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with pytest.raises(ValueError, match="Undeclared filterable field"):
        engine.query("pedang").filter_eq("tidak_ada", "x")


# ---------------------------------------------------------------------------
# Penghapusan, penulisan ulang, dan rebuild
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_document_removes_it_from_results(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents(
        [
            _document("ch1", "Pedang cahaya milik Aruna."),
            _document("ch2", "Aruna berjalan pulang."),
        ]
    )

    await engine.delete_document("ch1")

    hits = await engine.query("pedang").run()
    assert hits == []
    assert [hit.document_id for hit in await engine.query("aruna").run()] == ["ch2"]


@pytest.mark.asyncio
async def test_delete_documents_is_noop_for_empty_and_missing(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents([_document("ch1", "pedang")])

    await engine.delete_documents([])
    await engine.delete_documents(["tidak-ada"])

    assert await engine.count_chunks() == 1


@pytest.mark.asyncio
async def test_reindexing_same_document_replaces_old_chunks(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents([_document("ch1", "Versi lama menyebut pedang.")])
    await engine.index_documents([_document("ch1", "Versi baru menyebut tombak.")])

    assert await engine.count_chunks() == 1
    assert await engine.query("pedang").run() == []
    assert [hit.document_id for hit in await engine.query("tombak").run()] == ["ch1"]


@pytest.mark.asyncio
async def test_index_chunks_with_replace_document_ids(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents([_document("ch1", "teks pedang lama")])

    chunk = IndexChunk(
        document_id="ch1",
        chunk_index=0,
        raw_text="teks tombak baru",
        indexed_text="teks tombak baru",
        attributes={"project_id": "p1", "chapter_id": "ch1", "volume_id": "v1"},
        metadata={},
    )
    result = await engine.index_chunks([chunk], replace_document_ids={"ch1"})
    await engine.finalize_chunk_index()

    assert result.succeeded_chunk_count == 1
    assert await engine.count_chunks() == 1
    assert await engine.query("pedang").run() == []


@pytest.mark.asyncio
async def test_index_chunks_with_empty_list(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    result = await engine.index_chunks([])

    assert result.succeeded_chunk_count == 0


@pytest.mark.asyncio
async def test_rebuild_drops_previous_content(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents([_document("ch1", "pedang lama")])

    await engine.rebuild([_document("ch2", "tombak baru")])

    assert await engine.count_chunks() == 1
    assert await engine.query("pedang").run() == []
    assert [hit.document_id for hit in await engine.query("tombak").run()] == ["ch2"]


@pytest.mark.asyncio
async def test_rebuild_indexes_preserves_rows(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents([_document("ch1", "pedang cahaya")])

    await engine.rebuild_indexes()

    assert await engine.count_chunks() == 1
    assert [hit.document_id for hit in await engine.query("pedang").run()] == ["ch1"]


@pytest.mark.asyncio
async def test_drop_table_removes_database_file(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents([_document("ch1", "pedang")])
    assert engine.db_path.exists()

    await engine.drop_table()

    assert not engine.db_path.exists()
    assert await engine.count_chunks() == 0


@pytest.mark.asyncio
async def test_status_callbacks_are_reported(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    seen: list[tuple[str, str | None]] = []

    async def on_status_change(status: str, error: str | None) -> None:
        seen.append((status, error))

    await engine.index_documents(
        [_document("ch1", "pedang")], on_status_change=on_status_change
    )

    assert seen[0][0] == "building"
    assert seen[-1][0] == "ready"


@pytest.mark.asyncio
async def test_sync_status_callback_is_supported(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    seen: list[str] = []

    await engine.index_documents(
        [_document("ch1", "pedang")],
        on_status_change=lambda status, _error: seen.append(status),
    )

    assert seen[0] == "building"
    assert seen[-1] == "ready"


@pytest.mark.asyncio
async def test_document_without_text_is_reported_as_failure(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    result = await engine.index_documents([IndexDocument(document_id="ch1", text="")])

    assert result.succeeded_count == 0
    assert result.failed_count == 1
    assert "no chunks" in result.failed[0].error


@pytest.mark.asyncio
async def test_long_text_is_split_into_multiple_chunks(tmp_path: Path) -> None:
    engine = _engine(tmp_path, chunk_size=120)
    paragraphs = "\n\n".join(
        f"Paragraf {index} membahas pedang." for index in range(12)
    )
    await engine.index_documents([_document("ch1", paragraphs)])

    assert await engine.count_chunks() > 1
    hits = await engine.query("pedang").run()
    assert hits and all(hit.document_id == "ch1" for hit in hits)


# ---------------------------------------------------------------------------
# Regresi temuan staging cloud-only
# ---------------------------------------------------------------------------


def test_search_chapters_description_reflects_active_adapter(monkeypatch) -> None:
    """Agent harus diberi tahu bahwa pencarian bersifat leksikal di mode FTS5."""
    from app.agent_runtime.tools.impls.chapter.search_chapters import (
        _build_search_chapters_description,
    )

    monkeypatch.setattr("app.settings.settings.cloud_only", True)
    keyword_description = _build_search_chapters_description()

    monkeypatch.setattr("app.settings.settings.cloud_only", False)
    vector_description = _build_search_chapters_description()

    assert "KATA KUNCI" in keyword_description
    assert "leksikal" in keyword_description
    assert "vektor" not in keyword_description
    assert "vektor" in vector_description


def test_keyword_only_model_has_stable_identity(monkeypatch) -> None:
    """Model tiruan harus konsisten agar pemeriksaan rebuild tidak salah picu."""
    monkeypatch.setattr("app.settings.settings.cloud_only", True)
    from app.retrieval.chapter_index import build_keyword_only_model

    first = build_keyword_only_model()
    second = build_keyword_only_model()

    assert first.id == second.id == KEYWORD_ONLY_EMBEDDING_REF_ID
    assert first.task_type == "embedding"
    assert first.dimensions == KEYWORD_ONLY_DIMENSIONS
    assert is_keyword_only_model_ref(first.id)


@pytest.mark.asyncio
async def test_prefix_metadata_is_indexed_but_not_returned(tmp_path: Path) -> None:
    """Prefiks bab boleh membantu pencocokan tanpa mengotori teks hasil."""
    engine = _engine(tmp_path)
    await engine.index_documents(
        [
            IndexDocument(
                document_id="ch7",
                text="Isi bab tanpa menyebut nomor.",
                attributes={"project_id": "p1", "chapter_id": "ch7", "volume_id": "v1"},
                metadata={"prefix": "Bab tujuh Menara Kembar"},
            )
        ]
    )

    by_prefix = await engine.query("Menara Kembar").run()
    assert [hit.document_id for hit in by_prefix] == ["ch7"]
    assert by_prefix[0].text == "Isi bab tanpa menyebut nomor."


# ---------------------------------------------------------------------------
# filter_in dan filter_range
# ---------------------------------------------------------------------------


def _numeric_contract() -> RetrievalIndexContract:
    return RetrievalIndexContract(
        embedding_model_ref_id=KEYWORD_ONLY_EMBEDDING_REF_ID,
        embedding_model_id_snapshot=KEYWORD_ONLY_EMBEDDING_REF_ID,
        embedding_dimensions_snapshot=KEYWORD_ONLY_DIMENSIONS,
        chunk_size=400,
        chunk_overlap=40,
        filterable_fields=[
            FilterableField(name="project_id", field_type=FilterableFieldType.STRING),
            FilterableField(
                name="chapter_order", field_type=FilterableFieldType.INTEGER
            ),
        ],
    )


def _numeric_engine(tmp_path: Path) -> SqliteFtsRetrievalEngine:
    return SqliteFtsRetrievalEngine(
        base_dir=tmp_path,
        table_name="idx_numeric",
        contract=_numeric_contract(),
    )


def _ordered_document(doc_id: str, order: int) -> IndexDocument:
    return IndexDocument(
        document_id=doc_id,
        text="Pedang cahaya berkilau.",
        attributes={"project_id": "p1", "chapter_order": order},
        metadata={},
    )


@pytest.mark.asyncio
async def test_filter_in_matches_any_listed_value(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    await engine.index_documents(
        [
            _document("ch1", "Pedang cahaya pertama.", project_id="p1"),
            _document("ch2", "Pedang cahaya kedua.", project_id="p2"),
            _document("ch3", "Pedang cahaya ketiga.", project_id="p3"),
        ]
    )

    hits = (
        await engine.query("pedang cahaya")
        .filter_in("project_id", ["p1", "p3"])
        .run()
    )

    assert sorted(hit.document_id for hit in hits) == ["ch1", "ch3"]


@pytest.mark.asyncio
async def test_filter_in_rejects_empty_and_undeclared(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with pytest.raises(ValueError, match="at least one value"):
        engine.query("pedang").filter_in("project_id", [])
    with pytest.raises(ValueError, match="Undeclared filterable field"):
        engine.query("pedang").filter_in("tidak_ada", ["x"])


@pytest.mark.asyncio
async def test_filter_range_compares_numerically_not_lexicographically(
    tmp_path: Path,
) -> None:
    """Kolom filterable disimpan sebagai TEXT, jadi rentang wajib di-CAST.

    Tanpa CAST, SQLite membandingkan sebagai teks sehingga "10" jatuh sebelum
    "9" dan bab ke-10 lolos dari saringan ``lte=9``.
    """
    engine = _numeric_engine(tmp_path)
    await engine.index_documents(
        [_ordered_document(f"ch{order}", order) for order in (2, 9, 10, 11)]
    )

    hits = await engine.query("pedang cahaya").filter_range("chapter_order", lte=9).run()

    assert sorted(hit.document_id for hit in hits) == ["ch2", "ch9"]


@pytest.mark.asyncio
async def test_filter_range_supports_both_bounds(tmp_path: Path) -> None:
    engine = _numeric_engine(tmp_path)
    await engine.index_documents(
        [_ordered_document(f"ch{order}", order) for order in (1, 5, 9, 20)]
    )

    hits = (
        await engine.query("pedang cahaya")
        .filter_range("chapter_order", gte=5, lte=9)
        .run()
    )

    assert sorted(hit.document_id for hit in hits) == ["ch5", "ch9"]


@pytest.mark.asyncio
async def test_filter_range_requires_at_least_one_bound(tmp_path: Path) -> None:
    engine = _numeric_engine(tmp_path)

    with pytest.raises(ValueError, match="at least one bound"):
        engine.query("pedang").filter_range("chapter_order")


@pytest.mark.asyncio
async def test_filters_compose_across_methods(tmp_path: Path) -> None:
    engine = _numeric_engine(tmp_path)
    await engine.index_documents(
        [_ordered_document(f"ch{order}", order) for order in (3, 7, 12)]
    )

    hits = (
        await engine.query("pedang cahaya")
        .filter_eq("project_id", "p1")
        .filter_in("chapter_order", [3, 12])
        .filter_range("chapter_order", gte=10)
        .run()
    )

    assert [hit.document_id for hit in hits] == ["ch12"]
