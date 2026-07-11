# -*- coding: utf-8 -*-
"""Project chapter retrieval index integration service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities.model import Model
from app.models.repos import model_repo
from app.retrieval.service import OpenFicRetrievalService
from app.retrieval.internal.indexing.chunking import RecursiveCharacterChunker
from app.retrieval.types import (
    BatchIndexResult,
    DocumentIndexFailure,
    DocumentIndexSuccess,
    FilterableField,
    FilterableFieldType,
    IndexChunk,
    IndexDocument,
    RetrievalIndexContract,
)
from app.storage.models.chapter import Chapter
from app.storage.models.retrieval_chapter_index_state import RetrievalChapterIndexState
from app.storage.repos import (
    chapter_repo,
    project_repo,
    retrieval_chapter_index_state_repo,
    retrieval_index_repo,
    setting_repo,
)

CHAPTER_INDEX_STATUS_NOT_INDEXED = "not_indexed"
CHAPTER_INDEX_STATUS_QUEUED = "queued"
CHAPTER_INDEX_STATUS_INDEXING = "indexing"
CHAPTER_INDEX_STATUS_READY = "ready"
CHAPTER_INDEX_STATUS_STALE = "stale"
CHAPTER_INDEX_STATUS_FAILED = "failed"
CHAPTER_INDEX_STATUS_NEEDS_REBUILD = "needs_rebuild"
CHAPTER_INDEX_ITEM_TYPE = "retrieval_chapter"
SETTING_KEY_DEFAULT_EMBEDDING_MODEL = "default_embedding_model"

SETTING_KEY_INDEX_MODE = "index_mode"
SETTING_KEY_INDEX_ENABLED_PROJECTS = "index_enabled_projects"
SETTING_KEY_INDEX_CHUNK_SIZE = "index_chunk_size"
SETTING_KEY_INDEX_CHUNK_OVERLAP = "index_chunk_overlap"
SETTING_KEY_INDEX_AUTO_STRATEGY = "index_auto_strategy"
SETTING_KEY_INDEX_RERANK_ENABLED = "index_rerank_enabled"
SETTING_KEY_DEFAULT_RERANK_MODEL = "default_rerank_model"

INDEX_MODE_OFF = "off"
INDEX_MODE_ALL = "all"
INDEX_MODE_SELECTED = "selected"
INDEX_AUTO_STRATEGY_IMMEDIATE = "immediate"
INDEX_AUTO_STRATEGY_AGENT_DECIDED = "agent_decided"
INDEX_AUTO_STRATEGY_OFF = "off"

DEFAULT_INDEX_MODE = INDEX_MODE_OFF
DEFAULT_INDEX_AUTO_STRATEGY = INDEX_AUTO_STRATEGY_OFF
DEFAULT_INDEX_CHUNK_SIZE = 800
DEFAULT_INDEX_CHUNK_OVERLAP = 100
DEFAULT_INDEX_RERANK_ENABLED = False
DEFAULT_INDEX_RERANK_MODEL = ""

# 当前 chunk 表 schema 版本。提升该版本会令所有现存索引进入 needs_rebuild，
# 强制按新 schema（raw_text 列、章节前缀、ngram FTS）重建。
CURRENT_CHUNK_SCHEMA_VERSION = 2

# 面向中文全文检索的 FTS 索引参数：ngram bigram，关闭英文词干/停用词。
DEFAULT_FTS_INDEX_PARAMS: dict[str, Any] = {
    "base_tokenizer": "ngram",
    "ngram_min_length": 2,
    "ngram_max_length": 2,
    "stem": False,
    "remove_stop_words": False,
    "ascii_folding": False,
    "lower_case": True,
}

_VALID_INDEX_MODES = {INDEX_MODE_OFF, INDEX_MODE_ALL, INDEX_MODE_SELECTED}
_VALID_INDEX_AUTO_STRATEGIES = {
    INDEX_AUTO_STRATEGY_IMMEDIATE,
    INDEX_AUTO_STRATEGY_AGENT_DECIDED,
    INDEX_AUTO_STRATEGY_OFF,
}

# 索引状态汇总语义（面向用户/Agent，屏蔽内部细节）
INDEX_STATUS_DISABLED = "disabled"
INDEX_STATUS_NOT_CONFIGURED = "not_configured"
INDEX_STATUS_NO_CHAPTERS = "no_chapters"
INDEX_STATUS_NO_INDEX = "no_index"
INDEX_STATUS_INDEXING = "indexing"
INDEX_STATUS_NEEDS_REBUILD = "needs_rebuild"
INDEX_STATUS_STALE = "stale"
INDEX_STATUS_FRESH = "fresh"
INDEX_STATUS_FAILED = "failed"


class ChapterIndexNeedsRebuildError(RuntimeError):
    """Raised when a running chapter index item has become stale."""


class ChapterIndexContentChangedError(RuntimeError):
    """Raised when chapter content changes while its old content is indexing."""


class ChapterIndexOwnershipError(RuntimeError):
    """Raised when an old job item no longer owns a chapter index state."""


def chapter_index_key(project_id: str) -> str:
    return f"chapters:{project_id}"


def chapter_document_id(chapter_id: str) -> str:
    return f"chapter:{chapter_id}"


def _is_chapter_content_empty(chapter: Chapter) -> bool:
    return not (chapter.content or "").strip()


def compute_chapter_source_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _parse_int_setting(raw: str | None, *, default: int) -> int:
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value


def _parse_str_list_setting(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, str) and item]


@dataclass
class IndexSettingsConfig:
    """索引相关的全局设置快照。"""

    mode: str
    enabled_projects: set[str]
    chunk_size: int
    chunk_overlap: int
    auto_strategy: str
    embedding_model_ref_id: str
    rerank_enabled: bool
    rerank_model_ref_id: str


def _parse_bool_setting(raw: str | None, *, default: bool) -> bool:
    if raw is None or raw == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return default


async def get_index_settings(session: AsyncSession) -> IndexSettingsConfig:
    """读取索引相关的全部设置并校验为合法值。"""
    settings_list = await setting_repo.get_all(session)
    raw = {item.key: item.value for item in settings_list}

    mode = raw.get(SETTING_KEY_INDEX_MODE, DEFAULT_INDEX_MODE)
    if mode not in _VALID_INDEX_MODES:
        mode = DEFAULT_INDEX_MODE

    auto_strategy = raw.get(SETTING_KEY_INDEX_AUTO_STRATEGY, DEFAULT_INDEX_AUTO_STRATEGY)
    if auto_strategy not in _VALID_INDEX_AUTO_STRATEGIES:
        auto_strategy = DEFAULT_INDEX_AUTO_STRATEGY

    enabled_projects = set(
        _parse_str_list_setting(raw.get(SETTING_KEY_INDEX_ENABLED_PROJECTS))
    )
    chunk_size = _parse_int_setting(
        raw.get(SETTING_KEY_INDEX_CHUNK_SIZE), default=DEFAULT_INDEX_CHUNK_SIZE
    )
    chunk_overlap = _parse_int_setting(
        raw.get(SETTING_KEY_INDEX_CHUNK_OVERLAP), default=DEFAULT_INDEX_CHUNK_OVERLAP
    )
    embedding_model_ref_id = (raw.get(SETTING_KEY_DEFAULT_EMBEDDING_MODEL) or "").strip()
    rerank_enabled = _parse_bool_setting(
        raw.get(SETTING_KEY_INDEX_RERANK_ENABLED),
        default=DEFAULT_INDEX_RERANK_ENABLED,
    )
    rerank_model_ref_id = (raw.get(SETTING_KEY_DEFAULT_RERANK_MODEL) or "").strip()

    return IndexSettingsConfig(
        mode=mode,
        enabled_projects=enabled_projects,
        chunk_size=max(1, chunk_size),
        chunk_overlap=max(0, min(chunk_overlap, max(0, chunk_size - 1))),
        auto_strategy=auto_strategy,
        embedding_model_ref_id=embedding_model_ref_id,
        rerank_enabled=rerank_enabled,
        rerank_model_ref_id=rerank_model_ref_id,
    )


def is_project_index_enabled(config: IndexSettingsConfig, project_id: str) -> bool:
    if config.mode == INDEX_MODE_ALL:
        return True
    if config.mode == INDEX_MODE_SELECTED:
        return project_id in config.enabled_projects
    return False


async def get_index_chunk_config(session: AsyncSession) -> tuple[int, int]:
    """读取分块参数（chunk_size, chunk_overlap）。"""
    config = await get_index_settings(session)
    return config.chunk_size, config.chunk_overlap


async def resolve_index_embedding_model(
    session: AsyncSession, config: IndexSettingsConfig
) -> Model | None:
    """根据设置解析可用的 embedding 模型，未配置或非法时返回 None。"""
    if not config.embedding_model_ref_id:
        return None
    model = await model_repo.get_by_id(session, config.embedding_model_ref_id)
    if model is None or model.task_type != "embedding" or model.dimensions is None:
        return None
    return model


@dataclass
class ProjectIndexStatus:
    """单个项目的索引状态汇总（面向用户，不含内部 ID）。"""

    project_id: str
    enabled: bool
    status: str
    title: str = ""
    total_chapters: int = 0
    indexed_count: int = 0
    pending_count: int = 0
    in_progress_count: int = 0
    failed_count: int = 0
    empty_content_count: int = 0
    last_error: str | None = None

    @property
    def progress(self) -> float:
        indexable = self.total_chapters - self.empty_content_count
        if indexable <= 0:
            return 0.0
        return self.indexed_count / indexable

    def to_payload(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "enabled": self.enabled,
            "status": self.status,
            "title": self.title,
            "total_chapters": self.total_chapters,
            "indexed_count": self.indexed_count,
            "pending_count": self.pending_count,
            "in_progress_count": self.in_progress_count,
            "failed_count": self.failed_count,
            "empty_content_count": self.empty_content_count,
            "last_error": self.last_error,
            "progress": self.progress,
        }


def _effective_chapter_status(
    chapter: Chapter,
    state: RetrievalChapterIndexState | None,
) -> str:
    """计算单章的有效索引状态（结合内容哈希实时判断是否过期）。"""
    if state is None:
        return CHAPTER_INDEX_STATUS_NOT_INDEXED
    if state.status in {CHAPTER_INDEX_STATUS_QUEUED, CHAPTER_INDEX_STATUS_INDEXING}:
        return state.status
    if state.status == CHAPTER_INDEX_STATUS_NEEDS_REBUILD:
        return CHAPTER_INDEX_STATUS_NEEDS_REBUILD
    if state.status == CHAPTER_INDEX_STATUS_FAILED:
        return CHAPTER_INDEX_STATUS_FAILED
    if state.status in {CHAPTER_INDEX_STATUS_READY, CHAPTER_INDEX_STATUS_STALE}:
        current_hash = compute_chapter_source_hash(chapter.content)
        if state.source_hash != current_hash:
            return CHAPTER_INDEX_STATUS_STALE
        return CHAPTER_INDEX_STATUS_READY
    return CHAPTER_INDEX_STATUS_NOT_INDEXED


async def compute_project_index_status(
    session: AsyncSession,
    *,
    project_id: str,
    title: str | None = None,
) -> ProjectIndexStatus:
    """计算单个项目的索引状态汇总。

    ``title`` 传入时直接使用；为 ``None`` 时按需查询项目标题。
    """
    config = await get_index_settings(session)
    enabled = is_project_index_enabled(config, project_id)
    chapters = await chapter_repo.list_by_project(session, project_id)
    total = len(chapters)

    if title is None:
        project = await project_repo.get_by_id(session, project_id)
        title = project.title if project else ""

    if not enabled:
        return ProjectIndexStatus(
            project_id=project_id,
            enabled=False,
            status=INDEX_STATUS_DISABLED,
            title=title,
            total_chapters=total,
        )

    model = await resolve_index_embedding_model(session, config)
    if model is None:
        return ProjectIndexStatus(
            project_id=project_id,
            enabled=True,
            status=INDEX_STATUS_NOT_CONFIGURED,
            title=title,
            total_chapters=total,
        )

    if total == 0:
        return ProjectIndexStatus(
            project_id=project_id,
            enabled=True,
            status=INDEX_STATUS_NO_CHAPTERS,
            title=title,
            total_chapters=0,
        )

    index_key = chapter_index_key(project_id)
    project_index = await retrieval_index_repo.get_by_index_key(session, index_key)
    # schema 升级：旧 schema_version 的索引整体需要重建，优先于其它状态判定。
    schema_outdated = (
        project_index is not None
        and project_index.schema_version < CURRENT_CHUNK_SCHEMA_VERSION
    )
    states = {
        state.chapter_id: state
        for state in await retrieval_chapter_index_state_repo.list_by_project(
            session, project_id=project_id, index_key=index_key
        )
    }

    indexed = 0
    pending = 0
    in_progress = 0
    failed = 0
    needs_rebuild = 0
    empty_content = 0
    last_error: str | None = None

    for chapter in chapters:
        if _is_chapter_content_empty(chapter):
            empty_content += 1
            continue
        effective = _effective_chapter_status(chapter, states.get(chapter.id))
        if schema_outdated and effective == CHAPTER_INDEX_STATUS_READY:
            needs_rebuild += 1
            pending += 1
            continue
        if effective == CHAPTER_INDEX_STATUS_READY:
            indexed += 1
        elif effective in {CHAPTER_INDEX_STATUS_QUEUED, CHAPTER_INDEX_STATUS_INDEXING}:
            in_progress += 1
        elif effective == CHAPTER_INDEX_STATUS_NEEDS_REBUILD:
            needs_rebuild += 1
            pending += 1
        elif effective == CHAPTER_INDEX_STATUS_FAILED:
            failed += 1
            pending += 1
            state = states.get(chapter.id)
            if state is not None and state.error_message and last_error is None:
                last_error = state.error_message
        else:
            pending += 1

    if in_progress > 0:
        status = INDEX_STATUS_INDEXING
    elif failed > 0 and indexed == 0:
        status = INDEX_STATUS_FAILED
    elif needs_rebuild > 0:
        status = INDEX_STATUS_NEEDS_REBUILD
    elif pending == 0:
        status = INDEX_STATUS_FRESH
    elif indexed == 0:
        status = INDEX_STATUS_NO_INDEX
    else:
        status = INDEX_STATUS_STALE

    return ProjectIndexStatus(
        project_id=project_id,
        enabled=True,
        status=status,
        title=title,
        total_chapters=total,
        indexed_count=indexed,
        pending_count=pending,
        in_progress_count=in_progress,
        failed_count=failed,
        empty_content_count=empty_content,
        last_error=last_error,
    )


@dataclass
class IndexEnqueueResult:
    """索引入队结果。"""

    enqueued_count: int
    skipped_count: int
    job_id: str | None = None


@dataclass
class ChunkBatchIndexProgress:
    """Chapters that became complete after one bounded embedding request."""

    completed_chapter_ids: list[str]


async def enqueue_project_index_update(
    session: AsyncSession,
    *,
    project_id: str,
) -> IndexEnqueueResult | None:
    """为项目入队所有需要更新的章节索引。

    返回 None 表示项目未启用索引或未配置可用 embedding 模型；
    返回 IndexEnqueueResult 表示已处理（enqueued_count 可能为 0，即无需更新）。
    不会提交事务，由调用方负责 commit 与通知。
    """
    from app.background.jobs import service as background_service
    from app.background.jobs.constants import JOB_TYPE_RETRIEVAL_CHAPTER_INDEX_BATCH

    config = await get_index_settings(session)
    if not is_project_index_enabled(config, project_id):
        return None
    model = await resolve_index_embedding_model(session, config)
    if model is None:
        return None

    chapters = await chapter_repo.list_by_project(session, project_id)
    if not chapters:
        return IndexEnqueueResult(enqueued_count=0, skipped_count=0)

    index_key = chapter_index_key(project_id)
    project_index = await retrieval_index_repo.get_by_index_key(session, index_key)
    # 模型或维度变更时标记整个项目索引需要重建
    if (
        project_index is not None
        and project_index.status != "needs_rebuild"
        and (
            project_index.embedding_model_ref_id != model.id
            or project_index.embedding_dimensions_snapshot != model.dimensions
        )
    ):
        project_index.status = "needs_rebuild"
        await retrieval_index_repo.update(session, project_index)
        await retrieval_chapter_index_state_repo.mark_project_needs_rebuild(
            session, project_id=project_id, index_key=index_key
        )
    # schema 升级：旧 schema_version 的索引必须重建。在计算 selected 前标记，
    # 使过期章节进入待索引集合。
    if (
        project_index is not None
        and project_index.schema_version < CURRENT_CHUNK_SCHEMA_VERSION
    ):
        project_index.status = "needs_rebuild"
        await retrieval_index_repo.update(session, project_index)
        await retrieval_chapter_index_state_repo.mark_project_needs_rebuild(
            session, project_id=project_id, index_key=index_key
        )

    states = {
        state.chapter_id: state
        for state in await retrieval_chapter_index_state_repo.list_by_project(
            session, project_id=project_id, index_key=index_key
        )
    }

    # 恢复因后端异常重启而卡在 indexing/queued 的章节状态。
    # 这些状态在运行中的后台任务被中断后会残留，导致项目永远显示"索引中"
    # 且无法重新入队。将其重置为 needs_rebuild 以便重新索引。
    for chapter in chapters:
        state = states.get(chapter.id)
        if state is None:
            continue
        if state.status in {CHAPTER_INDEX_STATUS_INDEXING, CHAPTER_INDEX_STATUS_QUEUED}:
            state.status = CHAPTER_INDEX_STATUS_NEEDS_REBUILD
            state.job_id = None
            state.item_id = None
            state.error_message = None
            await retrieval_chapter_index_state_repo.save(session, state)

    # 恢复因异常重启而卡在 building 的检索索引状态。
    index_row = await retrieval_index_repo.get_by_index_key(session, index_key)
    if index_row is not None and index_row.status == "building":
        index_row.status = "needs_rebuild"
        await retrieval_index_repo.update(session, index_row)

    # 空内容章节永远不会被索引，若因全局重建被标记为 needs_rebuild，
    # 需重置为 not_indexed，避免阻塞检索工具的新鲜度检查。
    for chapter in chapters:
        state = states.get(chapter.id)
        if state is None:
            continue
        if state.status == CHAPTER_INDEX_STATUS_NEEDS_REBUILD and _is_chapter_content_empty(chapter):
            state.status = CHAPTER_INDEX_STATUS_NOT_INDEXED
            state.job_id = None
            state.item_id = None
            state.error_message = None
            await retrieval_chapter_index_state_repo.save(session, state)

    selected = [
        chapter
        for chapter in chapters
        if not _is_chapter_content_empty(chapter)
        and _effective_chapter_status(chapter, states.get(chapter.id))
        in {
            CHAPTER_INDEX_STATUS_NOT_INDEXED,
            CHAPTER_INDEX_STATUS_STALE,
            CHAPTER_INDEX_STATUS_FAILED,
            CHAPTER_INDEX_STATUS_NEEDS_REBUILD,
        }
    ]
    if not selected:
        if index_row is not None and index_row.status not in {"ready", "needs_rebuild"}:
            index_row.status = "ready"
            index_row.last_ready_at = datetime.now(UTC)
            await retrieval_index_repo.update(session, index_row)
        return IndexEnqueueResult(enqueued_count=0, skipped_count=len(chapters))

    await ChapterIndexIntegrationService().ensure_project_index(
        session,
        project_id=project_id,
        model=model,
    )

    job = await background_service.submit_job(
        session,
        job_type=JOB_TYPE_RETRIEVAL_CHAPTER_INDEX_BATCH,
        payload={"project_id": project_id},
        context={"embedding_model_ref_id": model.id},
        subject_type="project",
        subject_id=project_id,
    )
    items = await background_service.create_items(
        session,
        job_id=job.id,
        items=[
            (
                f"chapter:{chapter.id}",
                CHAPTER_INDEX_ITEM_TYPE,
                {"project_id": project_id, "chapter_id": chapter.id},
                index,
            )
            for index, chapter in enumerate(selected)
        ],
    )
    await retrieval_chapter_index_state_repo.queue_chapters_for_job(
        session,
        project_id=project_id,
        index_key=index_key,
        chapter_ids=[chapter.id for chapter in selected],
        embedding_model_ref_id=model.id,
        job_id=job.id,
        item_ids_by_chapter_id={
            chapter.id: item.id for chapter, item in zip(selected, items, strict=True)
        },
    )

    return IndexEnqueueResult(
        enqueued_count=len(selected),
        skipped_count=len(chapters) - len(selected),
        job_id=job.id,
    )


async def maybe_enqueue_auto_index(
    session: AsyncSession,
    *,
    project_id: str,
) -> IndexEnqueueResult | None:
    """当自动索引策略为"立即"时入队更新；否则返回 None。"""
    config = await get_index_settings(session)
    if config.auto_strategy != INDEX_AUTO_STRATEGY_IMMEDIATE:
        return None
    if not is_project_index_enabled(config, project_id):
        return None
    return await enqueue_project_index_update(session, project_id=project_id)


async def safe_maybe_enqueue_auto_index(
    session: AsyncSession,
    *,
    project_id: str,
) -> None:
    """best-effort 的自动索引入队，避免章节写入因索引副作用失败。"""
    try:
        await maybe_enqueue_auto_index(session, project_id=project_id)
    except Exception as exc:
        logger.bind(project_id=project_id).warning(
            f"auto index enqueue skipped: {exc}"
        )


class ChapterIndexIntegrationService:
    """Coordinates chapter rows, per-chapter state, and vector documents."""

    def __init__(self, *, retrieval_service: Any | None = None) -> None:
        self.retrieval_service = retrieval_service or OpenFicRetrievalService()

    def build_chapter_document(self, chapter: Chapter) -> IndexDocument:
        source_hash = compute_chapter_source_hash(chapter.content)
        prefix = self._build_chapter_prefix(chapter)
        return IndexDocument(
            document_id=chapter_document_id(chapter.id),
            text=chapter.content,
            attributes={
                "project_id": chapter.project_id,
                "chapter_id": chapter.id,
                "volume_id": chapter.volume_id,
            },
            metadata={
                "source_type": "chapter",
                "project_id": chapter.project_id,
                "chapter_id": chapter.id,
                "volume_id": chapter.volume_id,
                "chapter_order": chapter.order,
                "chapter_title": chapter.title,
                "source_hash": source_hash,
                "prefix": prefix,
            },
        )

    @staticmethod
    def _build_chapter_prefix(chapter: Chapter) -> str:
        order = chapter.order
        title = (chapter.title or "").strip()
        if order is not None and title:
            return f"第{order}章 {title}"
        if order is not None:
            return f"第{order}章"
        if title:
            return title
        return ""

    def build_contract(
        self,
        model: Model,
        *,
        chunk_size: int = DEFAULT_INDEX_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_INDEX_CHUNK_OVERLAP,
    ) -> RetrievalIndexContract:
        if model.dimensions is None:
            raise ValueError("default_embedding_model 必须配置 embedding dimensions")
        return RetrievalIndexContract(
            embedding_model_ref_id=model.id,
            embedding_model_id_snapshot=model.model_id,
            embedding_dimensions_snapshot=model.dimensions,
            distance_metric="cosine",
            chunker_type="recursive_character",
            chunk_size=max(1, chunk_size),
            chunk_overlap=max(0, chunk_overlap),
            filterable_fields=[
                FilterableField(
                    name="project_id",
                    field_type=FilterableFieldType.STRING,
                ),
                FilterableField(
                    name="chapter_id",
                    field_type=FilterableFieldType.STRING,
                ),
                FilterableField(
                    name="volume_id",
                    field_type=FilterableFieldType.STRING,
                ),
            ],
            vector_index_type="ivf_hnsw_sq",
            vector_index_params={},
            fts_index_params=dict(DEFAULT_FTS_INDEX_PARAMS),
            schema_version=CURRENT_CHUNK_SCHEMA_VERSION,
        )

    async def ensure_project_index(
        self,
        session: AsyncSession,
        *,
        project_id: str,
        model: Model,
    ):
        chunk_size, chunk_overlap = await get_index_chunk_config(session)
        return await self.retrieval_service.register_index(
            session,
            chapter_index_key(project_id),
            self.build_contract(
                model,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            ),
            replace_contract_if_needs_rebuild=True,
        )

    async def get_state(
        self,
        session: AsyncSession,
        *,
        project_id: str,
        chapter_id: str,
    ) -> RetrievalChapterIndexState | None:
        return await retrieval_chapter_index_state_repo.get_by_project_and_chapter(
            session,
            project_id=project_id,
            chapter_id=chapter_id,
            index_key=chapter_index_key(project_id),
        )

    async def get_or_create_state(
        self,
        session: AsyncSession,
        chapter: Chapter,
    ) -> RetrievalChapterIndexState:
        state = await self.get_state(
            session,
            project_id=chapter.project_id,
            chapter_id=chapter.id,
        )
        if state is not None:
            return state
        state = RetrievalChapterIndexState(
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            index_key=chapter_index_key(chapter.project_id),
            status=CHAPTER_INDEX_STATUS_NOT_INDEXED,
        )
        return await retrieval_chapter_index_state_repo.save(session, state)

    async def mark_chapter_queued(
        self,
        session: AsyncSession,
        chapter: Chapter,
        *,
        embedding_model_ref_id: str,
        job_id: str,
        item_id: str,
    ) -> RetrievalChapterIndexState:
        state = await self.get_or_create_state(session, chapter)
        state.status = CHAPTER_INDEX_STATUS_QUEUED
        state.embedding_model_ref_id = embedding_model_ref_id
        state.job_id = job_id
        state.item_id = item_id
        state.error_message = None
        return await retrieval_chapter_index_state_repo.save(session, state)

    async def mark_chapter_stale_if_changed(
        self,
        session: AsyncSession,
        chapter: Chapter,
    ) -> RetrievalChapterIndexState | None:
        state = await self.get_state(
            session,
            project_id=chapter.project_id,
            chapter_id=chapter.id,
        )
        if state is None or state.source_hash is None:
            return state
        current_hash = compute_chapter_source_hash(chapter.content)
        if state.source_hash == current_hash:
            return state
        if state.status in {
            CHAPTER_INDEX_STATUS_QUEUED,
            CHAPTER_INDEX_STATUS_INDEXING,
        }:
            return state
        state.status = CHAPTER_INDEX_STATUS_STALE
        state.job_id = None
        state.item_id = None
        return await retrieval_chapter_index_state_repo.save(session, state)

    async def mark_chapter_stale_if_indexed(
        self,
        session: AsyncSession,
        chapter: Chapter,
    ) -> RetrievalChapterIndexState | None:
        state = await self.get_state(
            session,
            project_id=chapter.project_id,
            chapter_id=chapter.id,
        )
        if state is None or state.source_hash is None:
            return state
        if state.status in {
            CHAPTER_INDEX_STATUS_QUEUED,
            CHAPTER_INDEX_STATUS_INDEXING,
            CHAPTER_INDEX_STATUS_NEEDS_REBUILD,
        }:
            return state
        state.status = CHAPTER_INDEX_STATUS_STALE
        state.job_id = None
        state.item_id = None
        return await retrieval_chapter_index_state_repo.save(session, state)

    async def delete_chapter_index(self, session: AsyncSession, chapter: Chapter) -> None:
        await retrieval_chapter_index_state_repo.delete_by_chapter_id(
            session,
            chapter.id,
        )
        try:
            await self.retrieval_service.delete_document(
                session,
                chapter_index_key(chapter.project_id),
                chapter_document_id(chapter.id),
            )
        except Exception as exc:
            logger.bind(
                project_id=chapter.project_id,
                chapter_id=chapter.id,
            ).warning(f"delete retrieval chapter document failed: {exc}")

    async def index_chapter(
        self,
        session: AsyncSession,
        *,
        chapter_id: str,
        embedding_client: Any,
        embedding_model: Model,
        job_id: str | None = None,
        item_id: str | None = None,
    ) -> RetrievalChapterIndexState:
        chapter = await chapter_repo.get_by_id(session, chapter_id)
        if chapter is None:
            raise ValueError(f"章节不存在: {chapter_id}")
        if _is_chapter_content_empty(chapter):
            return await self.get_or_create_state(session, chapter)

        await self.ensure_project_index(
            session,
            project_id=chapter.project_id,
            model=embedding_model,
        )
        state = await self.get_or_create_state(session, chapter)
        self._raise_if_state_not_owned(
            state,
            expected_job_id=job_id,
            expected_item_id=item_id,
        )
        state.status = CHAPTER_INDEX_STATUS_INDEXING
        state.embedding_model_ref_id = embedding_model.id
        state.error_message = None
        await retrieval_chapter_index_state_repo.save(session, state)

        document = self.build_chapter_document(chapter)
        metadata_source_hash = (document.metadata or {}).get("source_hash")
        if not isinstance(metadata_source_hash, str):
            raise ValueError("chapter index document missing source_hash metadata")
        indexed_source_hash = metadata_source_hash
        try:
            result = await self.retrieval_service.index_documents(
                session,
                chapter_index_key(chapter.project_id),
                [document],
                embedding_client,
            )
        except Exception:
            await self._raise_if_snapshot_needs_rebuild(
                session,
                state=state,
                embedding_model_ref_id=embedding_model.id,
            )
            raise

        await self._raise_if_snapshot_needs_rebuild(
            session,
            state=state,
            embedding_model_ref_id=embedding_model.id,
        )
        self._raise_if_state_not_owned(
            state,
            expected_job_id=job_id,
            expected_item_id=item_id,
        )
        if result.succeeded_count != 1:
            error = (
                result.failed[0].error
                if result.failed
                else "chapter indexing produced no success"
            )
            raise RuntimeError(error)

        await session.refresh(chapter)
        current_source_hash = compute_chapter_source_hash(chapter.content)
        if current_source_hash != indexed_source_hash:
            self._raise_if_state_not_owned(
                state,
                expected_job_id=job_id,
                expected_item_id=item_id,
            )
            state.status = CHAPTER_INDEX_STATUS_STALE
            state.job_id = None
            state.item_id = None
            state.error_message = None
            await retrieval_chapter_index_state_repo.save(session, state)
            raise ChapterIndexContentChangedError(
                "chapter content changed during indexing"
            )

        state.status = CHAPTER_INDEX_STATUS_READY
        state.source_hash = indexed_source_hash
        state.embedding_model_ref_id = embedding_model.id
        state.chunk_count = result.succeeded[0].chunk_count
        state.indexed_at = datetime.now(UTC)
        state.error_message = None
        return await retrieval_chapter_index_state_repo.save(session, state)

    async def index_chapters(
        self,
        session: AsyncSession,
        *,
        chapter_ids: list[str],
        embedding_client: Any,
        embedding_model: Model,
        job_id: str,
    ) -> BatchIndexResult:
        if not chapter_ids:
            return BatchIndexResult(
                total_documents=0,
                succeeded_count=0,
                failed_count=0,
            )

        chapter_map: dict[str, Chapter] = {}
        for cid in chapter_ids:
            chapter = await chapter_repo.get_by_id(session, cid)
            if chapter is None:
                raise ValueError(f"章节不存在: {cid}")
            chapter_map[cid] = chapter

        chapter_map = {
            cid: ch for cid, ch in chapter_map.items()
            if not _is_chapter_content_empty(ch)
        }
        if not chapter_map:
            return BatchIndexResult(
                total_documents=len(chapter_ids),
                succeeded_count=0,
                failed_count=0,
            )

        project_ids = {ch.project_id for ch in chapter_map.values()}
        if len(project_ids) != 1:
            raise ValueError("批量索引要求所有章节属于同一项目")
        project_id = next(iter(project_ids))

        await self.ensure_project_index(
            session,
            project_id=project_id,
            model=embedding_model,
        )

        index_key = chapter_index_key(project_id)

        # Mark all states as INDEXING
        for cid, chapter in chapter_map.items():
            state = await self.get_or_create_state(session, chapter)
            self._raise_if_state_not_owned(
                state,
                expected_job_id=job_id,
                expected_item_id=None,
            )
            state.status = CHAPTER_INDEX_STATUS_INDEXING
            state.embedding_model_ref_id = embedding_model.id
            state.error_message = None
            await retrieval_chapter_index_state_repo.save(session, state)

        # Build documents
        documents: list[IndexDocument] = []
        indexed_source_hashes: dict[str, str] = {}
        for cid, chapter in chapter_map.items():
            document = self.build_chapter_document(chapter)
            documents.append(document)
            metadata_source_hash = (document.metadata or {}).get("source_hash")
            if isinstance(metadata_source_hash, str):
                indexed_source_hashes[cid] = metadata_source_hash

        # Batch index
        try:
            result = await self.retrieval_service.index_documents(
                session,
                index_key,
                documents,
                embedding_client,
            )
        except Exception as exc:
            for cid in chapter_map:
                ch_state: RetrievalChapterIndexState | None = await self.get_state(
                    session, project_id=project_id, chapter_id=cid
                )
                if ch_state is not None:
                    try:
                        await self._raise_if_snapshot_needs_rebuild(
                            session,
                            state=ch_state,
                            embedding_model_ref_id=embedding_model.id,
                        )
                    except ChapterIndexNeedsRebuildError:
                        continue
                    ch_state.status = CHAPTER_INDEX_STATUS_FAILED
                    ch_state.error_message = str(exc)
                    await retrieval_chapter_index_state_repo.save(session, ch_state)
            raise

        # Update per-chapter states
        succeeded_doc_ids = {s.document_id: s for s in result.succeeded}
        failed_doc_ids = {f.document_id: f for f in result.failed}
        final_succeeded: list[DocumentIndexSuccess] = []
        final_failed: list[DocumentIndexFailure] = list(result.failed)

        for cid, chapter in chapter_map.items():
            doc_id = chapter_document_id(cid)

            if doc_id in failed_doc_ids:
                s = await self.get_state(
                    session, project_id=project_id, chapter_id=cid
                )
                if s is not None:
                    s.status = CHAPTER_INDEX_STATUS_FAILED
                    s.error_message = failed_doc_ids[doc_id].error
                    await retrieval_chapter_index_state_repo.save(session, s)
                continue

            if doc_id not in succeeded_doc_ids:
                continue

            s = await self.get_state(
                session, project_id=project_id, chapter_id=cid
            )
            if s is None:
                continue

            # Check if state was reassigned to a different job
            if s.status == CHAPTER_INDEX_STATUS_QUEUED:
                del succeeded_doc_ids[doc_id]
                final_failed.append(
                    DocumentIndexFailure(
                        document_id=doc_id,
                        error="chapter index item ownership changed",
                    )
                )
                continue

            try:
                await self._raise_if_snapshot_needs_rebuild(
                    session,
                    state=s,
                    embedding_model_ref_id=embedding_model.id,
                )
            except ChapterIndexNeedsRebuildError:
                del succeeded_doc_ids[doc_id]
                final_failed.append(
                    DocumentIndexFailure(
                        document_id=doc_id,
                        error="default_embedding_model changed; needs rebuild",
                    )
                )
                continue

            await session.refresh(chapter)
            current_source_hash = compute_chapter_source_hash(chapter.content)
            indexed_hash = indexed_source_hashes.get(cid)
            if indexed_hash is not None and current_source_hash != indexed_hash:
                s.status = CHAPTER_INDEX_STATUS_STALE
                s.job_id = None
                s.item_id = None
                s.error_message = None
                await retrieval_chapter_index_state_repo.save(session, s)
                del succeeded_doc_ids[doc_id]
                final_failed.append(
                    DocumentIndexFailure(
                        document_id=doc_id,
                        error="chapter content changed during indexing",
                    )
                )
                continue

            success = succeeded_doc_ids[doc_id]
            s.status = CHAPTER_INDEX_STATUS_READY
            s.source_hash = indexed_source_hashes.get(cid)
            s.embedding_model_ref_id = embedding_model.id
            s.chunk_count = success.chunk_count
            s.indexed_at = datetime.now(UTC)
            s.error_message = None
            await retrieval_chapter_index_state_repo.save(session, s)
            final_succeeded.append(success)

        result = BatchIndexResult(
            total_documents=len(chapter_ids),
            succeeded_count=len(final_succeeded),
            failed_count=len(final_failed),
            succeeded=final_succeeded,
            failed=final_failed,
        )
        return result

    async def stream_index_chapters(
        self,
        session: AsyncSession,
        *,
        chapter_ids: list[str],
        embedding_client: Any,
        embedding_model: Model,
        job_id: str,
        max_chunks_per_batch: int,
        check_cancelled: Callable[[], Awaitable[None]] | None = None,
        on_chapter_started: Callable[[str], Awaitable[None]] | None = None,
    ) -> AsyncIterator[ChunkBatchIndexProgress]:
        """Index chapters through bounded chunk requests and yield completed chapters.

        A chapter may span requests, but its state becomes ready only after all of
        its chunks were persisted. Completed records are released immediately so
        memory use is bounded by the request buffer and active long chapters.
        """
        if max_chunks_per_batch < 1:
            raise ValueError("max_chunks_per_batch must be positive")

        if not chapter_ids:
            return

        first_chapter = await chapter_repo.get_by_id(session, chapter_ids[0])
        if first_chapter is None:
            raise ValueError(f"章节不存在: {chapter_ids[0]}")
        project_id = first_chapter.project_id
        await self.ensure_project_index(
            session,
            project_id=project_id,
            model=embedding_model,
        )
        chunk_size, chunk_overlap = await get_index_chunk_config(session)
        chunker = RecursiveCharacterChunker(chunk_size, chunk_overlap)
        index_key = chapter_index_key(project_id)
        buffered_chunks: list[IndexChunk] = []
        pending: dict[str, dict[str, Any]] = {}
        written_document_ids: set[str] = set()

        async def finalize_completed() -> list[str]:
            completed: list[str] = []
            for chapter_id, record in list(pending.items()):
                if record["remaining"] != 0 or not record["all_chunks_added"]:
                    continue
                chapter = record["chapter"]
                state = record["state"]
                await self._raise_if_snapshot_needs_rebuild(
                    session,
                    state=state,
                    embedding_model_ref_id=embedding_model.id,
                )
                await session.refresh(chapter)
                if compute_chapter_source_hash(chapter.content) != record["source_hash"]:
                    state.status = CHAPTER_INDEX_STATUS_STALE
                    state.job_id = None
                    state.item_id = None
                    state.error_message = None
                    await retrieval_chapter_index_state_repo.save(session, state)
                    raise ChapterIndexContentChangedError(
                        "chapter content changed during indexing"
                    )
                state.status = CHAPTER_INDEX_STATUS_READY
                state.source_hash = record["source_hash"]
                state.embedding_model_ref_id = embedding_model.id
                state.chunk_count = record["chunk_count"]
                state.indexed_at = datetime.now(UTC)
                state.error_message = None
                await retrieval_chapter_index_state_repo.save(session, state)
                del pending[chapter_id]
                completed.append(chapter_id)
            return completed

        async def flush_chunks() -> list[str]:
            if not buffered_chunks:
                return []
            if check_cancelled is not None:
                await check_cancelled()
            await session.commit()
            if check_cancelled is not None:
                await check_cancelled()
            document_ids = {chunk.document_id for chunk in buffered_chunks}
            await self.retrieval_service.index_chunk_batch(
                session,
                index_key,
                buffered_chunks,
                embedding_client,
                replace_document_ids=document_ids - written_document_ids,
            )
            written_document_ids.update(document_ids)
            for chunk in buffered_chunks:
                chapter_id = chunk.attributes.get("chapter_id") if chunk.attributes else None
                if isinstance(chapter_id, str):
                    pending[chapter_id]["remaining"] -= 1
            buffered_chunks.clear()
            return await finalize_completed()

        for chapter_id in chapter_ids:
            if check_cancelled is not None:
                await check_cancelled()
            chapter = await chapter_repo.get_by_id(session, chapter_id)
            if chapter is None:
                raise ValueError(f"章节不存在: {chapter_id}")
            if chapter.project_id != project_id:
                raise ValueError("批量索引要求所有章节属于同一项目")
            if _is_chapter_content_empty(chapter):
                continue

            state = await self.get_or_create_state(session, chapter)
            self._raise_if_state_not_owned(
                state,
                expected_job_id=job_id,
                expected_item_id=None,
            )
            state.status = CHAPTER_INDEX_STATUS_INDEXING
            state.embedding_model_ref_id = embedding_model.id
            state.error_message = None
            await retrieval_chapter_index_state_repo.save(session, state)
            if on_chapter_started is not None:
                await on_chapter_started(chapter_id)

            document = self.build_chapter_document(chapter)
            raw_chunks = chunker.split_text(document.text or "")
            if not raw_chunks:
                raise ValueError(f"章节无法分块: {chapter_id}")
            metadata = document.metadata or {}
            prefix = metadata.get("prefix")
            indexed_chunks = [
                f"{prefix}\n{raw}" if isinstance(prefix, str) and prefix else raw
                for raw in raw_chunks
            ]
            pending[chapter_id] = {
                "chapter": chapter,
                "state": state,
                "source_hash": metadata.get("source_hash"),
                "chunk_count": len(raw_chunks),
                "remaining": len(raw_chunks),
                "all_chunks_added": False,
            }

            for chunk_index, (raw_text, indexed_text) in enumerate(
                zip(raw_chunks, indexed_chunks, strict=True)
            ):
                if chunk_index == len(raw_chunks) - 1:
                    pending[chapter_id]["all_chunks_added"] = True
                buffered_chunks.append(
                    IndexChunk(
                        document_id=document.document_id,
                        chunk_index=chunk_index,
                        raw_text=raw_text,
                        indexed_text=indexed_text,
                        attributes=document.attributes,
                        metadata=document.metadata,
                    )
                )
                if len(buffered_chunks) == max_chunks_per_batch:
                    completed = await flush_chunks()
                    yield ChunkBatchIndexProgress(completed)

        completed = await flush_chunks()
        if completed:
            yield ChunkBatchIndexProgress(completed)
        await self.retrieval_service.finalize_chunk_index(session, index_key)

    @staticmethod
    def _raise_if_state_not_owned(
        state: RetrievalChapterIndexState,
        *,
        expected_job_id: str | None,
        expected_item_id: str | None,
    ) -> None:
        if expected_job_id is None or expected_item_id is None:
            return
        if state.job_id != expected_job_id or state.item_id != expected_item_id:
            raise ChapterIndexOwnershipError("chapter index item ownership changed")

    async def _raise_if_snapshot_needs_rebuild(
        self,
        session: AsyncSession,
        *,
        state: RetrievalChapterIndexState,
        embedding_model_ref_id: str,
    ) -> None:
        await session.refresh(state)
        setting = await setting_repo.get_by_key(
            session,
            SETTING_KEY_DEFAULT_EMBEDDING_MODEL,
        )
        current_model_ref_id = setting.value.strip() if setting is not None else ""
        if (
            state.status == CHAPTER_INDEX_STATUS_NEEDS_REBUILD
            or current_model_ref_id != embedding_model_ref_id
        ):
            state.status = CHAPTER_INDEX_STATUS_NEEDS_REBUILD
            state.job_id = None
            state.item_id = None
            state.error_message = None
            await retrieval_chapter_index_state_repo.save(session, state)
            raise ChapterIndexNeedsRebuildError(
                "default_embedding_model changed; retrieval chapter index item needs rebuild"
            )
