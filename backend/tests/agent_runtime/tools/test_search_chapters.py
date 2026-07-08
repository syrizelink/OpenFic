import json
import importlib
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.agents.definitions import get_default_agent_definition
from app.agent_runtime.agents.tool_categories import get_tool_names_for_categories
from app.agent_runtime.tools.permission_metadata import (
    get_default_agent_tool_permissions,
    get_default_tool_permission_mode,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.core.encryption import EncryptionService
from app.models.repos import model_provider_repo, model_repo
from app.retrieval.chapter_index import compute_chapter_source_hash
from app.retrieval.types import ChunkSearchResult
from app.settings import settings
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.retrieval_chapter_index_state import (
    RetrievalChapterIndexState,
)
from app.storage.models.retrieval_index import RetrievalIndex
from app.storage.models.volume import Volume
from app.storage.repos import setting_repo


@dataclass
class FakeEmbeddingClient:
    config: Any


class FakeQueryBuilder:
    def __init__(self, results: list[ChunkSearchResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, Any]] = []

    def hybrid(self):
        self.calls.append(("hybrid", None))
        return self

    def vector(self):
        self.calls.append(("vector", None))
        return self

    def bm25(self):
        self.calls.append(("bm25", None))
        return self

    def vector_top_k(self, count: int):
        self.calls.append(("vector_top_k", count))
        return self

    def bm25_top_k(self, count: int):
        self.calls.append(("bm25_top_k", count))
        return self

    def rrf(self, *, k: int):
        self.calls.append(("rrf", k))
        return self

    def rerank(self, rerank_client, *, top_n=None):
        self.calls.append(("rerank", (rerank_client, top_n)))
        return self

    def ef(self, ef: int):
        self.calls.append(("ef", ef))
        return self

    def filter_eq(self, field: str, value: Any):
        self.calls.append(("filter_eq", (field, value)))
        return self

    def limit(self, count: int):
        self.calls.append(("limit", count))
        return self

    async def run(self) -> list[ChunkSearchResult]:
        self.calls.append(("run", None))
        return self.results


class FakeRetrievalService:
    def __init__(self, results: list[ChunkSearchResult]) -> None:
        self.results = results
        self.queries: list[tuple[str, str]] = []
        self.last_builder: FakeQueryBuilder | None = None

    async def query(self, session, index_key: str, text: str, embedding_client):
        _ = (session, embedding_client)
        self.queries.append((index_key, text))
        self.last_builder = FakeQueryBuilder(self.results)
        return self.last_builder


class FailingQueryRetrievalService:
    def __init__(self, message: str) -> None:
        self.message = message
        self.queries: list[tuple[str, str]] = []

    async def query(self, session, index_key: str, text: str, embedding_client):
        _ = (session, embedding_client)
        self.queries.append((index_key, text))
        raise RuntimeError(self.message)


def _make_state(project_id: str = "project-search") -> dict[str, Any]:
    return {
        "session_id": "session-search",
        "project_id": project_id,
        "model_config": {},
        "active_agent": None,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "message_checkpoints": [],
        "user_request": "",
    }


def _make_search_chapters_tool(module):
    return module.SearchChaptersTool(_state=_make_state())


async def _create_project_with_chapters(
    session: AsyncSession,
    *,
    project_id: str = "project-search",
) -> tuple[Chapter, Chapter]:
    project = Project(id=project_id, title="检索项目")
    volume = Volume(id="volume-main", project_id=project.id, title="第一卷", order=1)
    ready_chapter = Chapter(
        id="chapter-ready",
        project_id=project.id,
        volume_id=volume.id,
        title="星桥",
        content="星桥旧文本",
        order=1,
        word_count=5,
    )
    stale_chapter = Chapter(
        id="chapter-stale",
        project_id=project.id,
        volume_id=volume.id,
        title="潮汐",
        content="潮汐新文本",
        order=2,
        word_count=6,
    )
    session.add(project)
    session.add(volume)
    session.add(ready_chapter)
    session.add(stale_chapter)
    await session.flush()
    return ready_chapter, stale_chapter


async def _create_embedding_model(
    session: AsyncSession,
    *,
    model_id: str = "text-embedding-test",
    task_type: str = "embedding",
    dimensions: int | None = 3,
):
    encryption = EncryptionService(settings.encryption_key)
    provider = await model_provider_repo.create(
        session,
        name="Embedding Provider",
        url="https://example.test/v1",
        api_key_encrypted=encryption.encrypt("secret"),
        provider_type="openai-compatible",
    )
    return await model_repo.create(
        session,
        name="Embedding Model",
        provider_id=provider.id,
        model_id=model_id,
        task_type=task_type,
        dimensions=dimensions,
    )


def _chunk(
    *,
    chapter_id: str,
    chunk_id: str,
    chunk_index: int,
    text: str,
    score: float,
    matched_by: str = "hybrid",
) -> ChunkSearchResult:
    return ChunkSearchResult(
        document_id=f"chapter:{chapter_id}",
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        text=text,
        metadata={
            "project_id": "project-search",
            "chapter_id": chapter_id,
            "volume_id": "metadata-volume",
            "chapter_title": "metadata-title",
        },
        score=score,
        matched_by=matched_by,  # type: ignore[arg-type]
    )


def test_search_chapters_is_registered_with_schema_and_default_permission() -> None:
    tool = ToolRegistry.get_tools(names=["search_chapters"], state=_make_state())[0]

    schema = tool.args_schema.model_json_schema()

    assert tool.name == "search_chapters"
    assert tool.access_level == "readonly"
    assert set(schema["properties"].keys()) == {"query", "force"}
    assert schema["required"] == ["query"]
    assert schema["properties"]["query"]["description"]
    assert schema["properties"]["force"]["description"]
    assert get_default_tool_permission_mode("search_chapters") == "allow"
    assert {"tool_name": "search_chapters", "mode": "allow"} in (
        get_default_agent_tool_permissions()
    )


def test_search_chapters_expands_from_chapter_read_for_default_agents() -> None:
    assert "search_chapters" in get_tool_names_for_categories(["chapter_read"])

    for agent_key in (
        "primary",
        "explorer",
        "composer",
        "auditor",
        "writer",
        "actor",
        "reviewer",
    ):
        definition = get_default_agent_definition(agent_key)
        assert "search_chapters" in get_tool_names_for_categories(
            definition.enabled_tool_categories
        )


@pytest.mark.asyncio
async def test_search_chapters_returns_json_error_without_default_embedding_model(
    session: AsyncSession,
) -> None:
    await _create_project_with_chapters(session)
    await session.commit()
    tool = ToolRegistry.get_tools(names=["search_chapters"], state=_make_state())[0]

    data = json.loads(
        await tool.ainvoke(
            {"query": "星桥"},
            config={"configurable": {"db_session": session}},
        )
    )

    assert "error" in data
    assert "default_embedding_model" in data["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("index_status", ["registered", "needs_rebuild"])
async def test_search_chapters_returns_text_when_project_index_is_not_ready(
    session: AsyncSession,
    index_status: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    model = await _create_embedding_model(session)
    await _create_project_with_chapters(session)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status=index_status,
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add(
        RetrievalChapterIndexState(
            project_id="project-search",
            chapter_id="chapter-ready",
            index_key="chapters:project-search",
            status="ready",
            source_hash="hash-ready",
            embedding_model_ref_id=model.id,
            chunk_count=1,
        )
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()
    retrieval = FakeRetrievalService(
        [
            _chunk(
                chapter_id="chapter-ready",
                chunk_id="c1",
                chunk_index=0,
                text="old",
                score=0.5,
            )
        ]
    )
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    result = await tool.ainvoke(
        {"query": "星桥"},
        config={"configurable": {"db_session": session}},
    )

    # 索引不可用时返回提示文本（非 JSON），且不执行检索。
    assert "索引" in result
    assert "更新" in result
    assert retrieval.queries == []


@pytest.mark.asyncio
async def test_search_chapters_groups_ready_and_stale_results_by_current_chapter(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    model = await _create_embedding_model(session)
    await _create_project_with_chapters(session)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status="ready",
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add_all(
        [
            RetrievalChapterIndexState(
                project_id="project-search",
                chapter_id="chapter-ready",
                index_key="chapters:project-search",
                status="ready",
                source_hash="hash-ready",
                embedding_model_ref_id=model.id,
                chunk_count=2,
            ),
            RetrievalChapterIndexState(
                project_id="project-search",
                chapter_id="chapter-stale",
                index_key="chapters:project-search",
                status="stale",
                source_hash="hash-stale",
                embedding_model_ref_id=model.id,
                chunk_count=1,
            ),
        ]
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()
    retrieval = FakeRetrievalService(
        [
            _chunk(
                chapter_id="chapter-ready",
                chunk_id="ready:0",
                chunk_index=0,
                text="星桥 matched",
                score=0.9,
            ),
            _chunk(
                chapter_id="chapter-ready",
                chunk_id="ready:1",
                chunk_index=1,
                text="星桥 second",
                score=0.7,
                matched_by="bm25",
            ),
            _chunk(
                chapter_id="chapter-stale",
                chunk_id="stale:0",
                chunk_index=0,
                text="潮汐 matched",
                score=0.8,
            ),
        ]
    )
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    data = json.loads(
        await tool.ainvoke(
            {"query": "星桥", "force": True},
            config={"configurable": {"db_session": session}},
        )
    )

    assert data == {
        "query": "星桥",
        "results": [
            {
                "chapter_title": "星桥",
                "volume_title": "第一卷",
                "chapter_order": 1,
                "chunks": [
                    {
                        "chunk_index": 0,
                        "text": "星桥 matched",
                        "score": 0.9,
                    },
                    {
                        "chunk_index": 1,
                        "text": "星桥 second",
                        "score": 0.7,
                    },
                ],
            },
            {
                "chapter_title": "潮汐",
                "volume_title": "第一卷",
                "chapter_order": 2,
                "chunks": [
                    {
                        "chunk_index": 0,
                        "text": "潮汐 matched",
                        "score": 0.8,
                    }
                ],
            },
        ],
    }
    assert retrieval.queries == [("chapters:project-search", "星桥")]
    assert retrieval.last_builder is not None
    assert retrieval.last_builder.calls == [
        ("hybrid", None),
        ("vector_top_k", 40),
        ("bm25_top_k", 40),
        ("ef", 200),
        ("filter_eq", ("project_id", "project-search")),
        ("limit", 5),
        ("run", None),
    ]


@pytest.mark.asyncio
async def test_search_chapters_allows_stale_only_indexed_chapters(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    model = await _create_embedding_model(session)
    await _create_project_with_chapters(session)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status="ready",
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add(
        RetrievalChapterIndexState(
            project_id="project-search",
            chapter_id="chapter-stale",
            index_key="chapters:project-search",
            status="stale",
            source_hash="hash-stale",
            embedding_model_ref_id=model.id,
            chunk_count=1,
        )
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()
    retrieval = FakeRetrievalService(
        [
            _chunk(
                chapter_id="chapter-stale",
                chunk_id="stale:0",
                chunk_index=0,
                text="stale-only matched",
                score=0.8,
            )
        ]
    )
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    data = json.loads(
        await tool.ainvoke(
            {"query": "潮汐", "force": True},
            config={"configurable": {"db_session": session}},
        )
    )

    assert data["results"] == [
        {
            "chapter_title": "潮汐",
            "volume_title": "第一卷",
            "chapter_order": 2,
            "chunks": [
                {
                    "chunk_index": 0,
                    "text": "stale-only matched",
                    "score": 0.8,
                }
            ],
        }
    ]


@pytest.mark.asyncio
async def test_search_chapters_skips_chunks_for_other_project_chapters(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    model = await _create_embedding_model(session)
    await _create_project_with_chapters(session)
    other_project = Project(id="project-other", title="其它项目")
    other_volume = Volume(
        id="volume-other",
        project_id=other_project.id,
        title="其它卷",
        order=1,
    )
    other_chapter = Chapter(
        id="chapter-other",
        project_id=other_project.id,
        volume_id=other_volume.id,
        title="不应泄露",
        content="跨项目正文",
        order=1,
        word_count=4,
    )
    session.add(other_project)
    session.add(other_volume)
    session.add(other_chapter)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status="ready",
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add_all(
        [
            RetrievalChapterIndexState(
                project_id="project-search",
                chapter_id="chapter-ready",
                index_key="chapters:project-search",
                status="ready",
                source_hash="hash-ready",
                embedding_model_ref_id=model.id,
                chunk_count=1,
            ),
            RetrievalChapterIndexState(
                project_id="project-other",
                chapter_id="chapter-other",
                index_key="chapters:project-other",
                status="ready",
                source_hash="hash-other",
                embedding_model_ref_id=model.id,
                chunk_count=1,
            ),
        ]
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()
    retrieval = FakeRetrievalService(
        [
            _chunk(
                chapter_id="chapter-ready",
                chunk_id="ready:0",
                chunk_index=0,
                text="当前项目结果",
                score=0.9,
            ),
            _chunk(
                chapter_id="chapter-other",
                chunk_id="other:0",
                chunk_index=0,
                text="跨项目结果",
                score=0.95,
            ),
        ]
    )
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    data = json.loads(
        await tool.ainvoke(
            {"query": "项目", "force": True},
            config={"configurable": {"db_session": session}},
        )
    )

    assert [item["chapter_title"] for item in data["results"]] == ["星桥"]
    assert "不应泄露" not in json.dumps(data, ensure_ascii=False)


@pytest.mark.asyncio
async def test_search_chapters_blocks_when_default_embedding_model_mismatches_index(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    old_model = await _create_embedding_model(session, model_id="old-embedding")
    new_model = await _create_embedding_model(session, model_id="new-embedding")
    await _create_project_with_chapters(session)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status="ready",
            embedding_model_ref_id=old_model.id,
            embedding_model_id_snapshot=old_model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add(
        RetrievalChapterIndexState(
            project_id="project-search",
            chapter_id="chapter-ready",
            index_key="chapters:project-search",
            status="ready",
            source_hash="hash-ready",
            embedding_model_ref_id=old_model.id,
            chunk_count=1,
        )
    )
    await setting_repo.upsert(session, "default_embedding_model", new_model.id)
    await session.commit()
    retrieval = FakeRetrievalService([])
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    result = await tool.ainvoke(
        {"query": "星桥"},
        config={"configurable": {"db_session": session}},
    )

    assert "更新索引" in result
    assert retrieval.queries == []


@pytest.mark.asyncio
async def test_search_chapters_blocks_when_embedding_dimensions_mismatch_index(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    model = await _create_embedding_model(session, dimensions=5)
    await _create_project_with_chapters(session)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status="ready",
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add(
        RetrievalChapterIndexState(
            project_id="project-search",
            chapter_id="chapter-ready",
            index_key="chapters:project-search",
            status="ready",
            source_hash="hash-ready",
            embedding_model_ref_id=model.id,
            chunk_count=1,
        )
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()
    retrieval = FakeRetrievalService([])
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    result = await tool.ainvoke(
        {"query": "星桥"},
        config={"configurable": {"db_session": session}},
    )

    assert "更新索引" in result
    assert retrieval.queries == []


@pytest.mark.asyncio
async def test_search_chapters_rejects_non_embedding_default_model(
    session: AsyncSession,
) -> None:
    model = await _create_embedding_model(
        session,
        model_id="chat-model",
        task_type="llm",
        dimensions=None,
    )
    await _create_project_with_chapters(session)
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()

    tool = ToolRegistry.get_tools(names=["search_chapters"], state=_make_state())[0]
    data = json.loads(
        await tool.ainvoke(
            {"query": "星桥"},
            config={"configurable": {"db_session": session}},
        )
    )

    assert "error" in data
    assert "不是 embedding 模型" in data["error"]


@pytest.mark.asyncio
async def test_search_chapters_rejects_embedding_model_without_dimensions(
    session: AsyncSession,
) -> None:
    model = await _create_embedding_model(session, dimensions=None)
    await _create_project_with_chapters(session)
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()

    tool = ToolRegistry.get_tools(names=["search_chapters"], state=_make_state())[0]
    data = json.loads(
        await tool.ainvoke(
            {"query": "星桥"},
            config={"configurable": {"db_session": session}},
        )
    )

    assert "error" in data
    assert "缺少 embedding dimensions" in data["error"]


@pytest.mark.asyncio
async def test_search_chapters_hides_embedding_client_init_error_details(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    model = await _create_embedding_model(session)
    await _create_project_with_chapters(session)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status="ready",
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add(
        RetrievalChapterIndexState(
            project_id="project-search",
            chapter_id="chapter-ready",
            index_key="chapters:project-search",
            status="ready",
            source_hash="hash-ready",
            embedding_model_ref_id=model.id,
            chunk_count=1,
        )
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()
    sensitive = "provider secret sk-provider /tmp/provider-config"

    def fail_decrypt(self, provider):
        _ = (self, provider)
        raise RuntimeError(sensitive)

    retrieval = FakeRetrievalService([])
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(
        module.ModelProviderService,
        "get_decrypted_api_key",
        fail_decrypt,
    )

    tool = _make_search_chapters_tool(module)
    data = json.loads(
        await tool.ainvoke(
            {"query": "星桥", "force": True},
            config={"configurable": {"db_session": session}},
        )
    )

    assert "error" in data
    assert "embedding client 初始化失败" in data["error"]
    assert "sk-provider" not in data["error"]
    assert "/tmp/provider-config" not in data["error"]
    assert retrieval.queries == []


@pytest.mark.asyncio
async def test_search_chapters_hides_external_retrieval_error_details(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    model = await _create_embedding_model(session)
    await _create_project_with_chapters(session)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status="ready",
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add(
        RetrievalChapterIndexState(
            project_id="project-search",
            chapter_id="chapter-ready",
            index_key="chapters:project-search",
            status="ready",
            source_hash="hash-ready",
            embedding_model_ref_id=model.id,
            chunk_count=1,
        )
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()
    sensitive = "provider api key sk-secret LanceDB /tmp/private-table"
    retrieval = FailingQueryRetrievalService(sensitive)
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    data = json.loads(
        await tool.ainvoke(
            {"query": "星桥", "force": True},
            config={"configurable": {"db_session": session}},
        )
    )

    assert "error" in data
    assert "章节检索执行失败" in data["error"]
    assert "sk-secret" not in data["error"]
    assert "LanceDB" not in data["error"]
    assert "/tmp/private-table" not in data["error"]


@pytest.mark.asyncio
async def test_search_chapters_returns_empty_results(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    model = await _create_embedding_model(session)
    await _create_project_with_chapters(session)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status="ready",
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add(
        RetrievalChapterIndexState(
            project_id="project-search",
            chapter_id="chapter-ready",
            index_key="chapters:project-search",
            status="ready",
            source_hash="hash-ready",
            embedding_model_ref_id=model.id,
            chunk_count=1,
        )
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    await session.commit()
    retrieval = FakeRetrievalService([])
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    data = json.loads(
        await tool.ainvoke(
            {"query": "无结果", "force": True},
            config={"configurable": {"db_session": session}},
        )
    )

    assert data == {"query": "无结果", "results": []}


class _FakeRerankClient:
    """rerank client 替身：将传入文档按原顺序返回 0.99/0.51/... 的递减分数。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], int | None]] = []

    async def rerank(self, query: str, documents: list[str], top_n: int | None = None):
        self.calls.append((query, documents, top_n))
        scores = [0.99, 0.51, 0.4, 0.35]
        from app.models.clients.rerank_client import RerankItem, RerankResponse

        results = [
            RerankItem(index=i, relevance_score=scores[i % len(scores)])
            for i in range(len(documents))
        ]
        return RerankResponse(results=results, model="fake-reranker")


async def _seed_ready_index(session: AsyncSession) -> Any:
    """构造一个 fresh 可检索的项目索引，返回 (module, retrieval, model)。"""
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")
    model = await _create_embedding_model(session)
    await _create_project_with_chapters(session)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status="ready",
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add(
        RetrievalChapterIndexState(
            project_id="project-search",
            chapter_id="chapter-ready",
            index_key="chapters:project-search",
            status="ready",
            source_hash=compute_chapter_source_hash("星桥旧文本"),
            embedding_model_ref_id=model.id,
            chunk_count=1,
        )
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    return module, model


@pytest.mark.asyncio
async def test_search_chapters_rerank_path_uses_limited_top_n_and_invokes_rerank(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """启用 rerank 后候选池放大、最终上限收紧到 8 并调用 rerank。"""
    module, _ = await _seed_ready_index(session)
    await setting_repo.upsert(session, "index_rerank_enabled", "true")
    await setting_repo.upsert(session, "default_rerank_model", "rerank-model-1")
    await session.commit()

    rerank_client = _FakeRerankClient()
    monkeypatch.setattr(module, "_build_rerank_client", lambda *_a, **_k: _async_return(rerank_client))
    retrieval = FakeRetrievalService(
        [
            _chunk(
                chapter_id="chapter-ready",
                chunk_id="ready:0",
                chunk_index=0,
                text="星桥 matched",
                score=0.9,
            )
        ]
    )
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    await tool.ainvoke(
        {"query": "星桥", "force": True},
        config={"configurable": {"db_session": session}},
    )

    assert retrieval.last_builder is not None
    calls = retrieval.last_builder.calls
    assert ("vector_top_k", 40) in calls
    assert ("bm25_top_k", 40) in calls
    assert ("rerank", (rerank_client, 5)) in calls
    assert ("limit", 5) in calls


@pytest.mark.asyncio
async def test_search_chapters_drops_chunks_below_confidence_threshold(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """置信度低于 0.3 的分块应被丢弃，不进入返回结果。"""
    module, _ = await _seed_ready_index(session)
    await session.commit()
    retrieval = FakeRetrievalService(
        [
            _chunk(
                chapter_id="chapter-ready",
                chunk_id="ready:0",
                chunk_index=0,
                text="高相关",
                score=0.9,
            ),
            _chunk(
                chapter_id="chapter-ready",
                chunk_id="ready:1",
                chunk_index=1,
                text="低相关噪声",
                score=0.2,
            ),
            _chunk(
                chapter_id="chapter-ready",
                chunk_id="ready:2",
                chunk_index=2,
                text="中等相关",
                score=0.5,
            ),
        ]
    )
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    data = json.loads(
        await tool.ainvoke(
            {"query": "星桥", "force": True},
            config={"configurable": {"db_session": session}},
        )
    )

    chunks = data["results"][0]["chunks"]
    assert [c["chunk_index"] for c in chunks] == [0, 2]
    assert all(c["score"] >= 0.3 for c in chunks)


async def _async_return(value: Any) -> Any:
    return value


async def _seed_stale_index(session: AsyncSession) -> None:
    """构造一个"索引非最新"的项目：章节内容已变更但索引未更新。"""
    model = await _create_embedding_model(session)
    ready_chapter, _ = await _create_project_with_chapters(session)
    session.add(
        RetrievalIndex(
            index_key="chapters:project-search",
            table_name="chapters_project_search",
            status="ready",
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=3,
            schema_version=2,
        )
    )
    session.add(
        RetrievalChapterIndexState(
            project_id="project-search",
            chapter_id=ready_chapter.id,
            index_key="chapters:project-search",
            status="ready",
            source_hash=compute_chapter_source_hash("已变更的旧内容"),
            embedding_model_ref_id=model.id,
            chunk_count=1,
        )
    )
    await setting_repo.upsert(session, "default_embedding_model", model.id)


@pytest.mark.asyncio
async def test_search_chapters_returns_text_when_stale_and_not_forced(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    await _seed_stale_index(session)
    await session.commit()
    retrieval = FakeRetrievalService([])
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    result = await tool.ainvoke(
        {"query": "星桥"},
        config={"configurable": {"db_session": session}},
    )

    assert "不是最新" in result
    assert "force=true" in result
    assert "update_index" not in result
    assert retrieval.queries == []


@pytest.mark.asyncio
async def test_search_chapters_stale_text_appends_agent_decided_hint(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.search_chapters")

    await _seed_stale_index(session)
    await setting_repo.upsert(session, "index_auto_strategy", "agent_decided")
    await session.commit()
    retrieval = FakeRetrievalService([])
    monkeypatch.setattr(module, "OpenFicRetrievalService", lambda: retrieval)
    monkeypatch.setattr(module, "EmbeddingClient", FakeEmbeddingClient)

    tool = _make_search_chapters_tool(module)
    result = await tool.ainvoke(
        {"query": "星桥"},
        config={"configurable": {"db_session": session}},
    )

    assert "不是最新" in result
    assert "update_index" in result


@pytest.mark.asyncio
async def test_update_index_tool_enqueues_outdated_chapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.retrieval.chapter_index import IndexEnqueueResult

    module = importlib.import_module("app.agent_runtime.tools.impls.chapter.update_index")

    async def _noop_commit(_session) -> None:
        return None

    async def _fake_enqueue(_session, *, project_id):
        return IndexEnqueueResult(enqueued_count=1, skipped_count=0, job_id="job-1")

    monkeypatch.setattr(module, "enqueue_project_index_update", _fake_enqueue)
    monkeypatch.setattr(module, "schedule_emit_index_status", lambda *_a, **_k: None)
    monkeypatch.setattr(module.background_service, "commit_and_notify", _noop_commit)
    monkeypatch.setattr(module, "create_session", _fake_create_session)

    tool = module.UpdateIndexTool(_state=_make_state())
    result = await tool.ainvoke({}, config={"configurable": {"db_session": None}})

    assert "1 个章节" in result
    assert "已开始更新" in result

    # 无需更新
    async def _fake_enqueue_none(_session, *, project_id):
        return IndexEnqueueResult(enqueued_count=0, skipped_count=1)

    monkeypatch.setattr(module, "enqueue_project_index_update", _fake_enqueue_none)
    result = await tool.ainvoke({}, config={"configurable": {"db_session": None}})
    assert "已是最新" in result

    # 未启用
    async def _fake_enqueue_disabled(_session, *, project_id):
        return None

    monkeypatch.setattr(module, "enqueue_project_index_update", _fake_enqueue_disabled)
    result = await tool.ainvoke({}, config={"configurable": {"db_session": None}})
    assert "未启用" in result


class _FakeSession:
    async def close(self) -> None:
        return None

    async def commit(self) -> None:
        return None


async def _fake_create_session() -> _FakeSession:
    return _FakeSession()
