# -*- coding: utf-8 -*-
"""
Tests for retrieval service.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest
import lancedb  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.models.clients.embedding_client import EmbeddingClientConfigLike
from app.models.repos import model_provider_repo, model_repo
from app.retrieval.service import OpenFicRetrievalService
from app.retrieval.types import (
    FilterableField,
    FilterableFieldType,
    IndexChunk,
    IndexDocument,
    RetrievalIndexContract,
)
from app.models.clients.rerank_client import RerankItem, RerankResponse
from app.settings import settings
from app.storage.models.retrieval_index import RetrievalIndex


@dataclass
class FakeEmbeddingConfig:
    model_id: str
    dimensions: int | None


@dataclass
class FakeEmbeddingResponse:
    embeddings: list[list[float]]
    model: str
    usage: None = None


class FakeEmbeddingClient:
    config: EmbeddingClientConfigLike

    def __init__(self, model_id: str = "test-embedding", dimensions: int = 3):
        self.config = FakeEmbeddingConfig(model_id=model_id, dimensions=dimensions)
        self.embed_calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> FakeEmbeddingResponse:
        self.embed_calls.append(texts)
        return FakeEmbeddingResponse(
            embeddings=[self._embed_text(text) for text in texts],
            model=self.config.model_id,
        )

    async def embed_single(self, text: str) -> list[float]:
        return self._embed_text(text)

    @staticmethod
    def _embed_text(text: str) -> list[float]:
        normalized = text.lower()
        return [
            1.0 if "dragon" in normalized else 0.0,
            1.0 if "hero" in normalized else 0.0,
            1.0 if "guild" in normalized else 0.0,
        ]


class AlwaysFailEmbeddingClient(FakeEmbeddingClient):
    async def embed(self, texts: list[str]) -> FakeEmbeddingResponse:
        raise RuntimeError(f"embedding failed for {texts[0]}")


class CommitCheckingChunkEngine:
    def __init__(self, get_commit_count) -> None:
        self.get_commit_count = get_commit_count

    async def index_chunks(self, chunks, embedding_client, *, replace_document_ids=None):
        _ = (chunks, embedding_client, replace_document_ids)
        assert self.get_commit_count() > 0
        return type("Result", (), {"succeeded_chunk_count": len(chunks)})()


class FakeRerankClient:
    async def rerank(self, query: str, documents: list[str], top_n: int | None = None):
        return RerankResponse(
            results=[
                RerankItem(index=1, relevance_score=0.99),
                RerankItem(index=0, relevance_score=0.51),
            ],
            model="fake-reranker",
            usage={"total_tokens": 5},
        )


def _make_contract(embedding_model_ref_id: str) -> RetrievalIndexContract:
    return RetrievalIndexContract(
        embedding_model_ref_id=embedding_model_ref_id,
        embedding_model_id_snapshot="test-embedding",
        embedding_dimensions_snapshot=3,
        distance_metric="cosine",
        chunker_type="recursive_character",
        chunk_size=64,
        chunk_overlap=8,
        filterable_fields=[
            FilterableField(name="project_id", field_type=FilterableFieldType.STRING),
            FilterableField(name="chapter_order", field_type=FilterableFieldType.INTEGER),
        ],
        vector_index_type="ivf_hnsw_sq",
        vector_index_params={"m": 8, "ef_construction": 64},
        fts_index_params={"language": "English", "stem": True},
        schema_version=1,
    )


async def _create_embedding_model(session: AsyncSession):
    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name="Test Provider",
        url="https://openrouter.ai/api/v1",
        api_key_encrypted=encrypted_key,
        provider_type="openrouter",
    )

    model = await model_repo.create(
        session=session,
        name="Embedding Model",
        provider_id=provider.id,
        model_id="test-embedding",
        task_type="embedding",
        dimensions=3,
    )
    await session.commit()
    return model


async def _create_embedding_model_with_dimensions(
    session: AsyncSession,
    *,
    model_id: str,
    dimensions: int,
):
    encryption_service = EncryptionService(settings.encryption_key)
    encrypted_key = encryption_service.encrypt("test-key")

    provider = await model_provider_repo.create(
        session=session,
        name=f"Test Provider {model_id}",
        url=f"https://{model_id}.example.com",
        api_key_encrypted=encrypted_key,
        provider_type="openrouter",
    )

    model = await model_repo.create(
        session=session,
        name=f"Embedding Model {model_id}",
        provider_id=provider.id,
        model_id=model_id,
        task_type="embedding",
        dimensions=dimensions,
    )
    await session.commit()
    return model


@pytest.mark.asyncio
async def test_register_index_is_idempotent_for_same_contract(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)

    first = await service.register_index(session, "chapters", contract)
    second = await service.register_index(session, "chapters", contract)

    count = await session.scalar(select(func.count()).select_from(RetrievalIndex))

    assert first.index_key == "chapters"
    assert second.id == first.id
    assert count == 1


@pytest.mark.asyncio
async def test_register_index_keeps_needs_rebuild_for_same_contract(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    row = await service.register_index(session, "chapters", contract)
    row.status = "needs_rebuild"
    await session.commit()

    same_contract_row = await service.register_index(session, "chapters", contract)

    assert same_contract_row.id == row.id
    assert same_contract_row.status == "needs_rebuild"


@pytest.mark.asyncio
async def test_register_index_rejects_contract_mismatch(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    await service.register_index(session, "chapters", contract)

    different = RetrievalIndexContract(
        **{**contract.model_dump(), "chunk_size": 128}
    )

    with pytest.raises(ValueError):
        await service.register_index(session, "chapters", different)


@pytest.mark.asyncio
async def test_register_index_drops_existing_table_when_replacing_needs_rebuild_contract(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    old_model = await _create_embedding_model_with_dimensions(
        session,
        model_id="old-embedding",
        dimensions=3,
    )
    new_model = await _create_embedding_model_with_dimensions(
        session,
        model_id="new-embedding",
        dimensions=4,
    )
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    old_contract = RetrievalIndexContract(
        **{
            **_make_contract(old_model.id).model_dump(),
            "embedding_model_id_snapshot": "old-embedding",
        }
    )
    embedding_client = FakeEmbeddingClient(model_id="old-embedding", dimensions=3)
    await service.register_index(session, "chapters", old_contract)
    await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon.",
                attributes={"project_id": "p1", "chapter_order": 1},
            )
        ],
        embedding_client,
    )
    row = (await session.execute(select(RetrievalIndex))).scalar_one()
    table_name = row.table_name
    row.status = "needs_rebuild"
    await session.commit()

    db = await lancedb.connect_async(str(tmp_path / "lancedb"))
    assert table_name in list((await db.list_tables()).tables)

    new_contract = RetrievalIndexContract(
        **{
            **old_contract.model_dump(),
            "embedding_model_ref_id": new_model.id,
            "embedding_model_id_snapshot": "new-embedding",
            "embedding_dimensions_snapshot": 4,
        }
    )
    replaced = await service.register_index(
        session,
        "chapters",
        new_contract,
        replace_contract_if_needs_rebuild=True,
    )

    assert replaced.status == "registered"
    assert table_name not in list((await db.list_tables()).tables)


@pytest.mark.asyncio
async def test_index_and_query_happy_path(session: AsyncSession, tmp_path: Path) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    index_result = await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon and betrays the guild.",
                attributes={"project_id": "p1", "chapter_order": 1},
                metadata={"source": "chapter"},
            ),
            IndexDocument(
                document_id="chapter-2",
                text="A quiet village scene with no dragon at all.",
                attributes={"project_id": "p1", "chapter_order": 2},
                metadata={"source": "chapter"},
            ),
        ],
        embedding_client,
    )

    query = await service.query(session, "chapters", "hero dragon", embedding_client)
    results = await (
        query
        .hybrid()
        .filter_eq("project_id", "p1")
        .limit(1)
        .run()
    )

    assert index_result.succeeded_count == 2
    assert index_result.failed_count == 0
    assert len(results) == 1
    assert results[0].document_id == "chapter-1"
    assert results[0].matched_by in {"vector", "bm25", "hybrid"}


@pytest.mark.asyncio
async def test_index_documents_accepts_prechunked_input(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    result = await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                chunks=["The hero wakes.", "The dragon appears."],
                attributes={"project_id": "p1", "chapter_order": 1},
                metadata={"source": "prechunked"},
            )
        ],
        embedding_client,
        skip_chunking=True,
    )

    query = await service.query(session, "chapters", "dragon", embedding_client)
    results = await query.hybrid().limit(5).run()

    assert result.succeeded_count == 1
    assert result.succeeded[0].chunk_count == 2
    assert [row.chunk_index for row in results] == [1, 0]


@pytest.mark.asyncio
async def test_index_chunk_batches_append_one_chapter_without_reembedding_previous_chunks(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    first = await service.index_chunk_batch(
        session,
        "chapters",
        [
            IndexChunk(
                document_id="chapter-1",
                chunk_index=0,
                raw_text="The hero wakes.",
                indexed_text="Chapter 1\nThe hero wakes.",
                attributes={"project_id": "p1", "chapter_order": 1},
                metadata={"source": "chapter"},
            ),
            IndexChunk(
                document_id="chapter-1",
                chunk_index=1,
                raw_text="The dragon appears.",
                indexed_text="Chapter 1\nThe dragon appears.",
                attributes={"project_id": "p1", "chapter_order": 1},
                metadata={"source": "chapter"},
            ),
        ],
        embedding_client,
        replace_document_ids={"chapter-1"},
    )
    second = await service.index_chunk_batch(
        session,
        "chapters",
        [
            IndexChunk(
                document_id="chapter-1",
                chunk_index=2,
                raw_text="The hero escapes.",
                indexed_text="Chapter 1\nThe hero escapes.",
                attributes={"project_id": "p1", "chapter_order": 1},
                metadata={"source": "chapter"},
            )
        ],
        embedding_client,
    )
    await service.finalize_chunk_index(session, "chapters")

    query = await service.query(session, "chapters", "hero dragon", embedding_client)
    results = await query.hybrid().limit(5).run()

    assert first.succeeded_chunk_count == 2
    assert second.succeeded_chunk_count == 1
    assert embedding_client.embed_calls == [
        ["Chapter 1\nThe hero wakes.", "Chapter 1\nThe dragon appears."],
        ["Chapter 1\nThe hero escapes."],
    ]
    assert sorted(row.chunk_index for row in results) == [0, 1, 2]


@pytest.mark.asyncio
async def test_index_chunk_batch_commits_building_status_before_embedding(
    session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """索引状态写入不能持有 SQLite 写锁覆盖嵌入网络请求。"""
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    await service.register_index(session, "chapters", _make_contract(model.id))

    commit_count = 0
    original_commit = session.commit

    async def count_commit():
        nonlocal commit_count
        commit_count += 1
        await original_commit()

    monkeypatch.setattr(session, "commit", count_commit)
    engine = CommitCheckingChunkEngine(lambda: commit_count)
    monkeypatch.setattr(service, "_engine_for", lambda _row: engine)

    result = await service.index_chunk_batch(
        session,
        "chapters",
        [
            IndexChunk(
                document_id="chapter-1",
                chunk_index=0,
                raw_text="The hero wakes.",
                indexed_text="Chapter 1\nThe hero wakes.",
                attributes={"project_id": "p1", "chapter_order": 1},
            )
        ],
        FakeEmbeddingClient(),
    )

    assert result.succeeded_chunk_count == 1


@pytest.mark.asyncio
async def test_index_documents_replace_existing_document(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon.",
                attributes={"project_id": "p1", "chapter_order": 1},
            )
        ],
        embedding_client,
    )
    await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero leaves the guild behind.",
                attributes={"project_id": "p1", "chapter_order": 1},
            )
        ],
        embedding_client,
    )

    query = await service.query(session, "chapters", "guild", embedding_client)
    results = await query.hybrid().limit(5).run()

    assert [row.document_id for row in results] == ["chapter-1"]
    assert results[0].text == "The hero leaves the guild behind."


@pytest.mark.asyncio
async def test_query_supports_vector_bm25_hybrid_and_rerank(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon and joins the guild.",
                attributes={"project_id": "p1", "chapter_order": 1},
            ),
            IndexDocument(
                document_id="chapter-2",
                text="The guild turns on the hero after the feast.",
                attributes={"project_id": "p1", "chapter_order": 2},
            ),
        ],
        embedding_client,
    )

    query = await service.query(session, "chapters", "hero guild", embedding_client)
    vector_results = await query.vector().limit(2).run()
    bm25_results = await query.bm25().limit(2).run()
    baseline_hybrid_results = await query.hybrid().vector_top_k(2).bm25_top_k(2).limit(2).run()
    hybrid_results = await (
        query
        .hybrid()
        .vector_top_k(2)
        .bm25_top_k(2)
        .rrf(k=10)
        .rerank(FakeRerankClient(), top_n=2)
        .limit(2)
        .run()
    )

    assert vector_results[0].matched_by == "vector"
    assert bm25_results[0].matched_by == "bm25"
    assert [row.document_id for row in hybrid_results] == list(
        reversed([row.document_id for row in baseline_hybrid_results])
    )
    assert hybrid_results[0].rerank_score == 0.99
    assert hybrid_results[1].rerank_score == 0.51


@pytest.mark.asyncio
async def test_hybrid_rrf_score_normalized_to_confidence_range(
    session: AsyncSession, tmp_path: Path
) -> None:
    """未启用 rerank 时，最终 score 应归一化到 0~1 置信度区间。"""
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon and joins the guild.",
                attributes={"project_id": "p1", "chapter_order": 1},
            ),
            IndexDocument(
                document_id="chapter-2",
                text="The guild turns on the hero after the feast.",
                attributes={"project_id": "p1", "chapter_order": 2},
            ),
        ],
        embedding_client,
    )

    query = await service.query(session, "chapters", "hero guild", embedding_client)
    results = await query.hybrid().vector_top_k(2).bm25_top_k(2).limit(2).run()

    assert results
    for row in results:
        assert 0.0 <= row.score <= 1.0


@pytest.mark.asyncio
async def test_query_returns_raw_text_without_prefix_when_present(
    session: AsyncSession, tmp_path: Path
) -> None:
    """当文档带 prefix 元数据时，回传 text 应为正文（raw_text），不含前缀。"""
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon.",
                attributes={"project_id": "p1", "chapter_order": 1},
                metadata={"prefix": "第1章 序章"},
            )
        ],
        embedding_client,
    )

    query = await service.query(session, "chapters", "dragon", embedding_client)
    results = await query.hybrid().limit(5).run()

    assert results
    assert results[0].text == "The hero meets a dragon."


@pytest.mark.asyncio
async def test_query_supports_filter_in_and_filter_range(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon.",
                attributes={"project_id": "p1", "chapter_order": 1},
            ),
            IndexDocument(
                document_id="chapter-2",
                text="The guild turns against the hero.",
                attributes={"project_id": "p1", "chapter_order": 2},
            ),
            IndexDocument(
                document_id="chapter-3",
                text="Another dragon flies above the city.",
                attributes={"project_id": "p2", "chapter_order": 3},
            ),
        ],
        embedding_client,
    )

    query = await service.query(session, "chapters", "hero dragon guild", embedding_client)
    results = await (
        query
        .hybrid()
        .filter_in("project_id", ["p1"])
        .filter_range("chapter_order", gte=2)
        .limit(5)
        .run()
    )

    assert [row.document_id for row in results] == ["chapter-2"]


@pytest.mark.asyncio
async def test_delete_document_removes_rows(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon.",
                attributes={"project_id": "p1", "chapter_order": 1},
            )
        ],
        embedding_client,
    )

    await service.delete_document(session, "chapters", "chapter-1")

    query = await service.query(session, "chapters", "dragon", embedding_client)
    results = await query.hybrid().limit(5).run()

    assert results == []


@pytest.mark.asyncio
async def test_delete_document_ignores_missing_table(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")

    await service.register_index(session, "chapters", _make_contract(model.id))

    await service.delete_document(session, "chapters", "chapter-1")


@pytest.mark.asyncio
async def test_rebuild_replaces_table_contents(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon.",
                attributes={"project_id": "p1", "chapter_order": 1},
            )
        ],
        embedding_client,
    )

    await service.rebuild(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-2",
                text="A quiet village watches the guild parade.",
                attributes={"project_id": "p1", "chapter_order": 2},
            )
        ],
        embedding_client,
    )

    query = await service.query(session, "chapters", "guild", embedding_client)
    results = await query.hybrid().limit(5).run()

    assert [row.document_id for row in results] == ["chapter-2"]


@pytest.mark.asyncio
async def test_rebuild_indexes_keeps_queryable_state(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon.",
                attributes={"project_id": "p1", "chapter_order": 1},
            )
        ],
        embedding_client,
    )

    await service.rebuild_indexes(session, "chapters")

    query = await service.query(session, "chapters", "dragon", embedding_client)
    results = await query.hybrid().limit(5).run()

    assert [row.document_id for row in results] == ["chapter-1"]


@pytest.mark.asyncio
async def test_index_documents_stop_after_consecutive_failures(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = AlwaysFailEmbeddingClient()

    await service.register_index(session, "chapters", contract)
    result = await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(document_id=f"chapter-{index}", text=f"doc {index}")
            for index in range(6)
        ],
        embedding_client,
    )

    assert result.total_documents == 6
    assert result.failed_count == 6
    assert result.stopped_early is False
    assert len(result.failed) == 6
    for i in range(6):
        assert result.failed[i].document_id == f"chapter-{i}"


@pytest.mark.asyncio
async def test_index_documents_can_retry_after_failed_status(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)

    await service.register_index(session, "chapters", contract)
    failed_result = await service.index_documents(
        session,
        "chapters",
        [IndexDocument(document_id="chapter-1", text="dragon")],
        AlwaysFailEmbeddingClient(),
    )
    row = (await session.execute(select(RetrievalIndex))).scalar_one()
    assert failed_result.failed_count == 1
    assert row.status == "failed"

    retry_result = await service.index_documents(
        session,
        "chapters",
        [
            IndexDocument(
                document_id="chapter-1",
                text="The hero meets a dragon.",
                attributes={"project_id": "p1", "chapter_order": 1},
            )
        ],
        FakeEmbeddingClient(),
    )

    await session.refresh(row)
    assert retry_result.succeeded_count == 1
    assert row.status == "ready"


@pytest.mark.asyncio
async def test_index_documents_rejects_duplicate_document_ids(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)

    with pytest.raises(ValueError):
        await service.index_documents(
            session,
            "chapters",
            [
                IndexDocument(document_id="chapter-1", text="dragon"),
                IndexDocument(document_id="chapter-1", text="hero"),
            ],
            embedding_client,
        )


@pytest.mark.asyncio
async def test_index_documents_skip_chunking_requires_chunks_only(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")
    contract = _make_contract(model.id)
    embedding_client = FakeEmbeddingClient()

    await service.register_index(session, "chapters", contract)

    with pytest.raises(ValueError):
        await service.index_documents(
            session,
            "chapters",
            [
                IndexDocument(
                    document_id="chapter-1",
                    text="dragon",
                    chunks=["dragon"],
                )
            ],
            embedding_client,
            skip_chunking=True,
        )


@pytest.mark.asyncio
async def test_register_index_rejects_model_snapshot_mismatch(
    session: AsyncSession, tmp_path: Path
) -> None:
    model = await _create_embedding_model(session)
    service = OpenFicRetrievalService(base_dir=tmp_path / "lancedb")

    with pytest.raises(ValueError, match="Embedding dimensions snapshot mismatch"):
        await service.register_index(
            session,
            "chapters",
            RetrievalIndexContract(
                embedding_model_ref_id=model.id,
                embedding_model_id_snapshot="test-embedding",
                embedding_dimensions_snapshot=9,
                distance_metric="cosine",
                chunker_type="recursive_character",
                chunk_size=64,
                chunk_overlap=8,
                filterable_fields=[],
                vector_index_type="ivf_hnsw_sq",
                vector_index_params={},
                fts_index_params={},
                schema_version=1,
            ),
        )
