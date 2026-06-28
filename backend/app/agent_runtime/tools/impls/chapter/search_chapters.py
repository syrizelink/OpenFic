from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.registry import ToolRegistry
from app.core.encryption import EncryptionService
from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig
from app.models.clients.rerank_client import RerankClient, RerankConfig
from app.models.repos import model_provider_repo, model_repo
from app.models.services.model_provider_service import ModelProviderService
from app.retrieval.chapter_index import (
    CHAPTER_INDEX_STATUS_NEEDS_REBUILD,
    CHAPTER_INDEX_STATUS_READY,
    CHAPTER_INDEX_STATUS_STALE,
    CURRENT_CHUNK_SCHEMA_VERSION,
    INDEX_AUTO_STRATEGY_AGENT_DECIDED,
    INDEX_STATUS_FRESH,
    INDEX_STATUS_NEEDS_REBUILD,
    INDEX_STATUS_NO_INDEX,
    INDEX_STATUS_STALE,
    SETTING_KEY_DEFAULT_EMBEDDING_MODEL,
    chapter_index_key,
    compute_chapter_source_hash,
    get_index_settings,
)
from app.retrieval.service import OpenFicRetrievalService
from app.retrieval.types import ChunkSearchResult
from app.settings import settings
from app.storage.database import create_session
from app.storage.repos import (
    chapter_repo,
    retrieval_chapter_index_state_repo,
    retrieval_index_repo,
    setting_repo,
    volume_repo,
)

# 最终返回的分块上限。
SEARCH_CHAPTERS_CHUNK_LIMIT = 5
# 候选池放大：rerank 前从向量/FTS 各取的 top_k。
SEARCH_CHAPTERS_CANDIDATE_TOP_K = 40
# 置信度阈值：低于该值的分块视为不相关并丢弃。
SEARCH_CHAPTERS_CONFIDENCE_THRESHOLD = 0.3


class SearchChaptersInput(BaseModel):
    query: str = Field(description="用于检索项目章节内容的查询文本")
    force: bool = Field(
        default=False,
        description="是否忽略索引非最新状态，强制基于现有索引检索",
    )


class SearchChaptersChunkOutput(BaseModel):
    chunk_index: int
    text: str
    score: float


class SearchChaptersChapterOutput(BaseModel):
    chapter_title: str | None
    volume_title: str | None
    chapter_order: int | None
    chunks: list[SearchChaptersChunkOutput]


class SearchChaptersOutput(BaseModel):
    query: str
    results: list[SearchChaptersChapterOutput]


@asynccontextmanager
async def _tool_session(tool: AgentTool) -> AsyncIterator[AsyncSession]:
    runtime_session = tool.get_runtime_db_session()
    if runtime_session is not None:
        yield runtime_session
        return

    session = await create_session()
    try:
        yield session
    finally:
        await session.close()


async def _build_embedding_client(session: AsyncSession, model_ref_id: str):
    model = await model_repo.get_by_id(session, model_ref_id)
    if model is None or model.task_type != "embedding":
        raise ToolExecutionError("default_embedding_model 不存在或不是 embedding 模型")
    if model.dimensions is None:
        raise ToolExecutionError("default_embedding_model 缺少 embedding dimensions")
    provider = await model_provider_repo.get_by_id(session, model.provider_id)
    if provider is None:
        raise ToolExecutionError("default_embedding_model 关联的 provider 不存在")
    try:
        provider_service = ModelProviderService(EncryptionService(settings.encryption_key))
        api_key = provider_service.get_decrypted_api_key(provider) or ""
        return EmbeddingClient(
            EmbeddingConfig(
                provider_type=provider.provider_type,
                base_url=provider.url,
                api_key=api_key,
                model_id=model.model_id,
                dimensions=model.dimensions,
            )
        )
    except Exception as exc:
        if isinstance(exc, ToolExecutionError):
            raise
        raise ToolExecutionError("章节检索 embedding client 初始化失败") from exc


async def _build_rerank_client(
    session: AsyncSession, model_ref_id: str
) -> RerankClient | None:
    """构造 rerank client；模型缺失或类型不符时返回 None（降级为纯 RRF）。"""
    model = await model_repo.get_by_id(session, model_ref_id)
    if model is None or model.task_type != "rerank":
        return None
    provider = await model_provider_repo.get_by_id(session, model.provider_id)
    if provider is None:
        return None
    try:
        provider_service = ModelProviderService(EncryptionService(settings.encryption_key))
        api_key = provider_service.get_decrypted_api_key(provider) or ""
        return RerankClient(
            RerankConfig(
                provider_type=provider.provider_type,
                base_url=provider.url,
                api_key=api_key,
                model_id=model.model_id,
            )
        )
    except Exception:
        return None


def _metadata_chapter_id(result: ChunkSearchResult) -> str | None:
    chapter_id = result.metadata.get("chapter_id")
    return chapter_id if isinstance(chapter_id, str) and chapter_id else None


def _metadata_volume_id(result: ChunkSearchResult) -> str | None:
    volume_id = result.metadata.get("volume_id")
    return volume_id if isinstance(volume_id, str) and volume_id else None


async def _compute_index_freshness(
    session: AsyncSession,
    *,
    project_id: str,
    model: Any,
) -> str:
    """计算项目索引的新鲜度：fresh / stale / needs_rebuild / no_index。"""
    index_key = chapter_index_key(project_id)
    project_index = await retrieval_index_repo.get_by_index_key(session, index_key)
    if project_index is None:
        return INDEX_STATUS_NO_INDEX
    if (
        project_index.status == "needs_rebuild"
        or project_index.embedding_model_ref_id != model.id
        or project_index.embedding_dimensions_snapshot != model.dimensions
        or project_index.schema_version < CURRENT_CHUNK_SCHEMA_VERSION
    ):
        return INDEX_STATUS_NEEDS_REBUILD

    states = await retrieval_chapter_index_state_repo.list_by_project(
        session,
        project_id=project_id,
        index_key=index_key,
    )
    chapters = await chapter_repo.list_by_project(session, project_id)
    chapters_by_id = {chapter.id: chapter for chapter in chapters}

    has_searchable = False
    has_stale = False
    for state in states:
        chapter = chapters_by_id.get(state.chapter_id)
        if chapter is None:
            continue
        if not (chapter.content or "").strip():
            continue
        if state.status == CHAPTER_INDEX_STATUS_NEEDS_REBUILD:
            return INDEX_STATUS_NEEDS_REBUILD
        if state.status in {CHAPTER_INDEX_STATUS_READY, CHAPTER_INDEX_STATUS_STALE}:
            current_hash = compute_chapter_source_hash(chapter.content)
            if state.source_hash != current_hash:
                has_stale = True
                has_searchable = True
            else:
                has_searchable = True

    if not has_searchable:
        return INDEX_STATUS_NO_INDEX
    if has_stale:
        return INDEX_STATUS_STALE
    return INDEX_STATUS_FRESH


def _not_latest_text(
    *,
    freshness: str,
    auto_strategy: str,
) -> str:
    if freshness == INDEX_STATUS_NEEDS_REBUILD:
        return (
            "当前项目的检索索引不是最新的（嵌入模型或分块参数已变更），"
            "现有索引无法用于检索，需要先更新索引后才能检索章节内容。"
        )
    if freshness == INDEX_STATUS_NO_INDEX:
        return (
            "当前项目尚未建立可用的检索索引，无法检索章节内容。"
            "请先更新索引后再进行检索。"
        )
    # stale
    text = (
        "当前项目的检索索引不是最新的（部分章节内容已发生变更），"
        "此时不返回结构化检索结果。你可以：使用 force=true 强制基于现有索引检索，"
        "或先更新索引以获得完整结果。"
    )
    if auto_strategy == INDEX_AUTO_STRATEGY_AGENT_DECIDED:
        text += "\n当前自动索引策略为“由 Agent 决定”，建议调用 update_index 工具更新索引。"
    return text


def _group_results(
    *,
    query: str,
    results: list[ChunkSearchResult],
    chapters_by_id: dict[str, Any],
    volumes_by_id: dict[str, Any],
) -> str:
    grouped: OrderedDict[str, list[ChunkSearchResult]] = OrderedDict()
    fallback_volume_ids: dict[str, str | None] = {}
    for result in results:
        chapter_id = _metadata_chapter_id(result)
        if chapter_id is None:
            continue
        if chapter_id not in chapters_by_id:
            continue
        grouped.setdefault(chapter_id, []).append(result)
        fallback_volume_ids.setdefault(chapter_id, _metadata_volume_id(result))

    items: list[SearchChaptersChapterOutput] = []
    for chapter_id, chapter_results in grouped.items():
        chapter = chapters_by_id.get(chapter_id)
        vid = chapter.volume_id if chapter is not None else fallback_volume_ids.get(chapter_id)
        volume = volumes_by_id.get(vid) if vid else None
        items.append(
            SearchChaptersChapterOutput(
                chapter_title=chapter.title if chapter is not None else None,
                volume_title=volume.title if volume is not None else None,
                chapter_order=chapter.order if chapter is not None else None,
                chunks=[
                    SearchChaptersChunkOutput(
                        chunk_index=result.chunk_index,
                        text=result.text,
                        score=result.score,
                    )
                    for result in chapter_results
                ],
            )
        )

    return SearchChaptersOutput(query=query, results=items).model_dump_json()


@ToolRegistry.register
class SearchChaptersTool(AgentTool):
    name: str = "search_chapters"
    description: str = "按查询文本检索当前项目的章节内容，并按章节分组返回匹配片段。"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = SearchChaptersInput

    async def _execute(self, query: str, force: bool = False) -> str:
        async with _tool_session(self) as session:
            setting = await setting_repo.get_by_key(
                session,
                SETTING_KEY_DEFAULT_EMBEDDING_MODEL,
            )
            model_ref_id = setting.value.strip() if setting is not None else ""
            if not model_ref_id:
                raise ToolExecutionError("未配置 default_embedding_model，无法检索章节")
            model = await model_repo.get_by_id(session, model_ref_id)
            if model is None or model.task_type != "embedding":
                raise ToolExecutionError("default_embedding_model 不存在或不是 embedding 模型")
            if model.dimensions is None:
                raise ToolExecutionError("default_embedding_model 缺少 embedding dimensions")

            index_config = await get_index_settings(session)
            freshness = await _compute_index_freshness(
                session,
                project_id=self.project_id,
                model=model,
            )

            # 索引不可用（需重建或无索引）时，强制检索也无法绕过。
            if freshness in {INDEX_STATUS_NEEDS_REBUILD, INDEX_STATUS_NO_INDEX}:
                return _not_latest_text(
                    freshness=freshness,
                    auto_strategy=index_config.auto_strategy,
                )
            # 索引非最新（有过期章节）且未强制检索：返回提示文本。
            if freshness == INDEX_STATUS_STALE and not force:
                return _not_latest_text(
                    freshness=freshness,
                    auto_strategy=index_config.auto_strategy,
                )

            try:
                embedding_client = await _build_embedding_client(session, model_ref_id)
                logger.info("章节检索: embedding client 初始化完成 project_id={}", self.project_id)
                rerank_client: RerankClient | None = None
                if index_config.rerank_enabled and index_config.rerank_model_ref_id:
                    rerank_client = await _build_rerank_client(
                        session, index_config.rerank_model_ref_id
                    )
                final_limit = SEARCH_CHAPTERS_CHUNK_LIMIT
                builder = await OpenFicRetrievalService().query(
                    session,
                    chapter_index_key(self.project_id),
                    query,
                    embedding_client,
                )
                logger.info("章节检索: 查询构建器已创建 project_id={}", self.project_id)
                query_builder = (
                    builder.hybrid()
                    .vector_top_k(SEARCH_CHAPTERS_CANDIDATE_TOP_K)
                    .bm25_top_k(SEARCH_CHAPTERS_CANDIDATE_TOP_K)
                    .ef(200)
                    .filter_eq("project_id", self.project_id)
                )
                if rerank_client is not None:
                    query_builder = query_builder.rerank(
                        rerank_client, top_n=SEARCH_CHAPTERS_CHUNK_LIMIT
                    )
                logger.info("章节检索: 开始执行 LanceDB 查询 project_id={}", self.project_id)
                results = await query_builder.limit(final_limit).run()
                logger.info("章节检索: 查询完成 result_count={}", len(results))
            except Exception as exc:
                if isinstance(exc, ToolExecutionError):
                    raise
                logger.exception("章节检索执行失败: {}", exc)
                raise ToolExecutionError(
                    f"章节检索执行失败: {type(exc).__name__}"
                ) from exc
            if not results:
                return SearchChaptersOutput(query=query, results=[]).model_dump_json()

            # 置信度裁剪：丢弃低于阈值的不相关分块，降低上下文噪声。
            results = [
                result
                for result in results
                if result.score >= SEARCH_CHAPTERS_CONFIDENCE_THRESHOLD
            ]
            if not results:
                return SearchChaptersOutput(query=query, results=[]).model_dump_json()

            chapter_ids = [
                chapter_id
                for result in results
                if (chapter_id := _metadata_chapter_id(result)) is not None
            ]
            candidate_chapters = await chapter_repo.get_by_ids(
                session,
                list(dict.fromkeys(chapter_ids)),
            )
            chapters = [
                chapter
                for chapter in candidate_chapters
                if chapter.project_id == self.project_id
            ]
            volume_ids = list(dict.fromkeys(
                chapter.volume_id for chapter in chapters if chapter.volume_id
            ))
            volumes_by_id: dict[str, Any] = {}
            if volume_ids:
                volumes = await volume_repo.list_by_project(session, self.project_id)
                volumes_by_id = {v.id: v for v in volumes}
            return _group_results(
                query=query,
                results=results,
                chapters_by_id={chapter.id: chapter for chapter in chapters},
                volumes_by_id=volumes_by_id,
            )
