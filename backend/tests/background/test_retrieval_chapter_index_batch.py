# -*- coding: utf-8 -*-
"""Retrieval chapter index background job tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.background.events.publisher import BackgroundEventPublisher
from app.background.jobs.models import BackgroundJob, BackgroundJobItem
from app.background.jobs.states import JOB_STATUS_FAILED, JOB_STATUS_PENDING, JOB_STATUS_SUCCEEDED
from app.background.runtime.context import JobContext
from app.background.jobs.definitions import retrieval_chapter_index_batch as definition
from app.core.encryption import EncryptionService
from app.models.repos import model_provider_repo, model_repo
from app.retrieval.chapter_index import (
    ChapterIndexIntegrationService,
    ChunkBatchIndexProgress,
)
from app.retrieval.types import ChunkIndexResult
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.retrieval_chapter_index_state import RetrievalChapterIndexState
from app.storage.models.volume import Volume
from app.storage.repos import setting_repo


class FakeEmbeddingConfig:
    model_id = "fake-embedding"
    dimensions = 3


class FakeEmbeddingClient:
    config = FakeEmbeddingConfig()

    async def embed(self, texts):
        return None

    async def embed_single(self, text):
        return [0.0, 0.0, 0.0]


class FakeRetrievalService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def register_index(self, *args, **kwargs):
        return None

    async def index_chunk_batch(self, session, index_key, chunks, embedding_client, **kwargs):
        _ = (session, index_key, embedding_client, kwargs)
        if self.fail:
            raise RuntimeError("vector store failed")
        return ChunkIndexResult(succeeded_chunk_count=len(chunks))

    async def finalize_chunk_index(self, session, index_key):
        _ = (session, index_key)


class MutatingRetrievalService(FakeRetrievalService):
    def __init__(self, *, new_model_ref_id: str) -> None:
        super().__init__()
        self.new_model_ref_id = new_model_ref_id

    async def index_chunk_batch(self, session, index_key, chunks, embedding_client, **kwargs):
        payload = chunks[0].metadata or {}
        project_id = payload["project_id"]
        chapter_id = payload["chapter_id"]
        await setting_repo.upsert(
            session,
            "default_embedding_model",
            self.new_model_ref_id,
        )
        from sqlalchemy import select
        from sqlmodel import col

        state = (
            await session.execute(
                select(RetrievalChapterIndexState).where(
                    col(RetrievalChapterIndexState.project_id) == project_id,
                    col(RetrievalChapterIndexState.chapter_id) == chapter_id,
                    col(RetrievalChapterIndexState.index_key) == index_key,
                )
            )
        ).scalar_one()
        state.status = "needs_rebuild"
        state.error_message = None
        await session.flush()
        return await super().index_chunk_batch(
            session,
            index_key,
            chunks,
            embedding_client,
            **kwargs,
        )


class ContentChangingRetrievalService(FakeRetrievalService):
    async def index_chunk_batch(self, session, index_key, chunks, embedding_client, **kwargs):
        _ = (index_key, embedding_client, kwargs)
        from sqlalchemy import select
        from sqlmodel import col

        chapter_id = chunks[0].metadata["chapter_id"]
        chapter = (
            await session.execute(
                select(Chapter).where(col(Chapter.id) == chapter_id)
            )
        ).scalar_one()
        chapter.content = "英雄在索引期间改写了正文"
        await session.flush()
        return await super().index_chunk_batch(
            session,
            index_key,
            chunks,
            embedding_client,
            **kwargs,
        )


class StateReassigningChapterIndexService:
    def __init__(self, *, new_job_id: str, new_item_id: str, fail: bool = False) -> None:
        self.new_job_id = new_job_id
        self.new_item_id = new_item_id
        self.fail = fail

    async def stream_index_chapters(
        self,
        session,
        *,
        chapter_ids,
        embedding_client,
        embedding_model,
        job_id=None,
        max_chunks_per_batch,
    ):
        _ = (embedding_client, embedding_model, job_id, max_chunks_per_batch)
        if False:
            yield ChunkBatchIndexProgress([])
        from sqlalchemy import select
        from sqlmodel import col

        for chapter_id in chapter_ids:
            chapter = (
                await session.execute(
                    select(Chapter).where(col(Chapter.id) == chapter_id)
                )
            ).scalar_one()
            state = (
                await session.execute(
                    select(RetrievalChapterIndexState).where(
                        col(RetrievalChapterIndexState.project_id) == chapter.project_id,
                        col(RetrievalChapterIndexState.chapter_id) == chapter.id,
                        col(RetrievalChapterIndexState.index_key)
                        == f"chapters:{chapter.project_id}",
                    )
                )
            ).scalar_one()
            state.status = "queued"
            state.job_id = self.new_job_id
            state.item_id = self.new_item_id
            state.error_message = None
            await session.flush()
        if self.fail:
            raise RuntimeError("old job failed after new enqueue")
        raise RuntimeError("chapter index item ownership changed")


class FailingIfCalledChapterIndexService:
    def __init__(self) -> None:
        self.called = False

    async def index_chapters(self, *args, **kwargs):
        self.called = True
        raise AssertionError("stale embedding job must not index")


class MutatingFailingChapterIndexService:
    def __init__(self, *, project_id: str, chapter_id: str, new_model_ref_id: str) -> None:
        self.project_id = project_id
        self.chapter_id = chapter_id
        self.new_model_ref_id = new_model_ref_id

    async def stream_index_chapters(
        self,
        session,
        *,
        chapter_ids,
        embedding_client,
        embedding_model,
        job_id=None,
        max_chunks_per_batch,
    ):
        _ = (chapter_ids, embedding_client, embedding_model, job_id, max_chunks_per_batch)
        if False:
            yield ChunkBatchIndexProgress([])
        await setting_repo.upsert(
            session,
            "default_embedding_model",
            self.new_model_ref_id,
        )
        from sqlalchemy import select
        from sqlmodel import col

        state = (
            await session.execute(
                select(RetrievalChapterIndexState).where(
                    col(RetrievalChapterIndexState.project_id) == self.project_id,
                    col(RetrievalChapterIndexState.chapter_id) == self.chapter_id,
                    col(RetrievalChapterIndexState.index_key)
                    == f"chapters:{self.project_id}",
                )
            )
        ).scalar_one()
        state.status = "needs_rebuild"
        state.error_message = None
        await session.flush()
        raise RuntimeError("vector store failed")


async def _noop_check_cancelled() -> None:
    return None


async def _create_embedding_model(session: AsyncSession, model_id: str = "fake-embedding"):
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    provider = await model_provider_repo.create(
        session=session,
        name="Provider",
        url="https://api.test.com",
        api_key_encrypted=encryption_service.encrypt("test-key"),
        provider_type="openai",
    )
    return await model_repo.create(
        session=session,
        name="Embedding",
        provider_id=provider.id,
        model_id=model_id,
        task_type="embedding",
        dimensions=3,
    )


async def _seed_job(session: AsyncSession, *, fail: bool = False):
    model = await _create_embedding_model(session)
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    project = Project(id="project-1", title="项目", description="")
    volume = Volume(id="volume-1", project_id=project.id, title="第一卷", order=1)
    chapter = Chapter(
        id="chapter-1",
        project_id=project.id,
        volume_id=volume.id,
        title="第一章",
        content="英雄遇见龙",
        word_count=5,
        order=1,
    )
    job = BackgroundJob(
        type="retrieval_chapter_index_batch",
        status=JOB_STATUS_PENDING,
        payload_json='{"project_id":"project-1"}',
        context_json=f'{{"embedding_model_ref_id":"{model.id}"}}',
        subject_type="project",
        subject_id=project.id,
    )
    session.add(project)
    session.add(volume)
    session.add(chapter)
    session.add(job)
    await session.flush()
    item = BackgroundJobItem(
        job_id=job.id,
        item_key=f"chapter:{chapter.id}",
        type="retrieval_chapter",
        status=JOB_STATUS_PENDING,
        payload_json=f'{{"project_id":"{project.id}","chapter_id":"{chapter.id}"}}',
        order_index=0,
    )
    state = RetrievalChapterIndexState(
        project_id=project.id,
        chapter_id=chapter.id,
        index_key=f"chapters:{project.id}",
        status="queued",
        source_hash="old",
        embedding_model_ref_id=model.id,
        job_id=job.id,
        item_id=item.id,
    )
    session.add(item)
    session.add(state)
    await session.commit()
    return job, item, state, fail


@pytest.mark.asyncio
async def test_retrieval_chapter_index_batch_saves_ready_state(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, item, state, _ = await _seed_job(session)
    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: ChapterIndexIntegrationService(
            retrieval_service=FakeRetrievalService()
        ),
    )

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    result = await definition.handle_retrieval_chapter_index_batch(context)

    await session.refresh(item)
    await session.refresh(state)
    assert result == {"total": 1, "succeeded": 1, "failed": 0}
    assert item.status == JOB_STATUS_SUCCEEDED
    assert state.status == "ready"
    assert state.chunk_count == 1
    assert state.indexed_at is not None
    assert state.source_hash != "old"
    assert state.error_message is None


@pytest.mark.asyncio
async def test_retrieval_chapter_index_batch_saves_failed_state(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, item, state, _ = await _seed_job(session, fail=True)
    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: ChapterIndexIntegrationService(
            retrieval_service=FakeRetrievalService(fail=True)
        ),
    )

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await definition.handle_retrieval_chapter_index_batch(context)

    await session.refresh(item)
    await session.refresh(state)
    assert item.status == JOB_STATUS_FAILED
    assert state.status == "failed"
    assert state.error_message == "索引中止：vector store failed"


@pytest.mark.asyncio
async def test_retrieval_chapter_index_batch_rejects_stale_embedding_model_metadata(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_model = await _create_embedding_model(session, "old-embedding")
    new_model = await _create_embedding_model(session, "new-embedding")
    await setting_repo.upsert(session, "default_embedding_model", new_model.id)
    project = Project(id="project-stale", title="项目", description="")
    volume = Volume(id="volume-stale", project_id=project.id, title="第一卷", order=1)
    chapter = Chapter(
        id="chapter-stale",
        project_id=project.id,
        volume_id=volume.id,
        title="第一章",
        content="英雄遇见龙",
        word_count=5,
        order=1,
    )
    job = BackgroundJob(
        type="retrieval_chapter_index_batch",
        status=JOB_STATUS_PENDING,
        payload_json='{"project_id":"project-stale"}',
        context_json=f'{{"embedding_model_ref_id":"{old_model.id}"}}',
        subject_type="project",
        subject_id=project.id,
    )
    session.add(project)
    session.add(volume)
    session.add(chapter)
    session.add(job)
    await session.flush()
    item = BackgroundJobItem(
        job_id=job.id,
        item_key=f"chapter:{chapter.id}",
        type="retrieval_chapter",
        status=JOB_STATUS_PENDING,
        payload_json=f'{{"project_id":"{project.id}","chapter_id":"{chapter.id}"}}',
        order_index=0,
    )
    state = RetrievalChapterIndexState(
        project_id=project.id,
        chapter_id=chapter.id,
        index_key=f"chapters:{project.id}",
        status="needs_rebuild",
        source_hash="old",
        embedding_model_ref_id=old_model.id,
        job_id=job.id,
    )
    session.add(item)
    session.add(state)
    await session.commit()

    guarded_service = FailingIfCalledChapterIndexService()
    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: guarded_service,
    )

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await definition.handle_retrieval_chapter_index_batch(context)

    await session.refresh(item)
    await session.refresh(state)
    assert guarded_service.called is False
    assert item.status == JOB_STATUS_FAILED
    assert "default_embedding_model" in (item.error_json or "")
    assert state.status == "needs_rebuild"
    assert state.error_message is None


@pytest.mark.asyncio
async def test_retrieval_chapter_index_batch_preserves_needs_rebuild_if_failure_races_after_service_check(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, item, state, _ = await _seed_job(session)
    new_model = await _create_embedding_model(session, "new-embedding")
    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: MutatingFailingChapterIndexService(
            project_id=state.project_id,
            chapter_id=state.chapter_id,
            new_model_ref_id=new_model.id,
        ),
    )

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await definition.handle_retrieval_chapter_index_batch(context)

    await session.refresh(item)
    await session.refresh(state)
    assert item.status == JOB_STATUS_FAILED
    assert "vector store failed" in (item.error_json or "")
    assert state.status == "needs_rebuild"
    assert state.error_message is None


@pytest.mark.asyncio
async def test_retrieval_chapter_index_batch_preserves_needs_rebuild_if_settings_change_during_index(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, item, state, _ = await _seed_job(session)
    new_model = await _create_embedding_model(session, "new-embedding")
    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: ChapterIndexIntegrationService(
            retrieval_service=MutatingRetrievalService(
                new_model_ref_id=new_model.id,
            )
        ),
    )

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await definition.handle_retrieval_chapter_index_batch(context)

    await session.refresh(item)
    await session.refresh(state)
    assert item.status == JOB_STATUS_FAILED
    assert "default_embedding_model" in (item.error_json or "")
    assert state.status == "needs_rebuild"
    assert state.error_message is None


@pytest.mark.asyncio
async def test_retrieval_chapter_index_batch_marks_stale_if_content_changes_during_index(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, item, state, _ = await _seed_job(session)
    state.item_id = item.id
    await session.commit()
    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: ChapterIndexIntegrationService(
            retrieval_service=ContentChangingRetrievalService()
        ),
    )

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await definition.handle_retrieval_chapter_index_batch(context)

    await session.refresh(item)
    await session.refresh(state)
    assert item.status == JOB_STATUS_FAILED
    assert "chapter content changed during indexing" in (item.error_json or "")
    assert state.status == "stale"
    assert state.job_id is None
    assert state.item_id is None
    assert state.error_message is None


@pytest.mark.asyncio
async def test_retrieval_chapter_index_batch_does_not_overwrite_new_job_state_on_old_success(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, item, state, _ = await _seed_job(session)
    state.item_id = item.id
    new_job = BackgroundJob(
        type="retrieval_chapter_index_batch",
        status=JOB_STATUS_PENDING,
        payload_json='{"project_id":"project-1"}',
        context_json=job.context_json,
        subject_type="project",
        subject_id=state.project_id,
    )
    session.add(new_job)
    await session.flush()
    new_item = BackgroundJobItem(
        job_id=new_job.id,
        item_key=f"chapter:{state.chapter_id}",
        type="retrieval_chapter",
        status=JOB_STATUS_PENDING,
        payload_json=f'{{"project_id":"{state.project_id}","chapter_id":"{state.chapter_id}"}}',
        order_index=0,
    )
    session.add(new_item)
    await session.commit()
    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: StateReassigningChapterIndexService(
            new_job_id=new_job.id,
            new_item_id=new_item.id,
        ),
    )

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await definition.handle_retrieval_chapter_index_batch(context)

    await session.refresh(item)
    await session.refresh(state)
    assert item.status == JOB_STATUS_FAILED
    assert "chapter index item ownership changed" in (item.error_json or "")
    assert state.status == "queued"
    assert state.job_id == new_job.id
    assert state.item_id == new_item.id
    assert state.error_message is None


@pytest.mark.asyncio
async def test_retrieval_chapter_index_batch_does_not_overwrite_new_job_state_on_old_failure(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, item, state, _ = await _seed_job(session)
    state.item_id = item.id
    new_job = BackgroundJob(
        type="retrieval_chapter_index_batch",
        status=JOB_STATUS_PENDING,
        payload_json='{"project_id":"project-1"}',
        context_json=job.context_json,
        subject_type="project",
        subject_id=state.project_id,
    )
    session.add(new_job)
    await session.flush()
    new_item = BackgroundJobItem(
        job_id=new_job.id,
        item_key=f"chapter:{state.chapter_id}",
        type="retrieval_chapter",
        status=JOB_STATUS_PENDING,
        payload_json=f'{{"project_id":"{state.project_id}","chapter_id":"{state.chapter_id}"}}',
        order_index=0,
    )
    session.add(new_item)
    await session.commit()
    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: StateReassigningChapterIndexService(
            new_job_id=new_job.id,
            new_item_id=new_item.id,
            fail=True,
        ),
    )

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await definition.handle_retrieval_chapter_index_batch(context)

    await session.refresh(item)
    await session.refresh(state)
    assert item.status == JOB_STATUS_FAILED
    assert "old job failed after new enqueue" in (item.error_json or "")
    assert state.status == "queued"
    assert state.job_id == new_job.id
    assert state.item_id == new_item.id
    assert state.error_message is None


class MultiDocumentRetrievalService:
    """处理多文档的检索服务替身：所有文档都成功。"""

    async def register_index(self, *args, **kwargs):
        return None

    async def index_chunk_batch(self, session, index_key, chunks, embedding_client, **kwargs):
        _ = (session, index_key, embedding_client, kwargs)
        return ChunkIndexResult(succeeded_chunk_count=len(chunks))

    async def finalize_chunk_index(self, session, index_key):
        _ = (session, index_key)


async def _seed_multi_chapter_job(
    session: AsyncSession, *, chapter_count: int
):
    """创建含多个章节的索引任务，返回 (job, items, states)。"""
    model = await _create_embedding_model(session)
    await setting_repo.upsert(session, "default_embedding_model", model.id)
    project = Project(id="project-multi", title="多章项目", description="")
    volume = Volume(id="volume-multi", project_id=project.id, title="卷", order=1)
    session.add(project)
    session.add(volume)

    job = BackgroundJob(
        type="retrieval_chapter_index_batch",
        status=JOB_STATUS_PENDING,
        payload_json='{"project_id":"project-multi"}',
        context_json=f'{{"embedding_model_ref_id":"{model.id}"}}',
        subject_type="project",
        subject_id=project.id,
    )
    session.add(job)
    await session.flush()

    items = []
    states = []
    for i in range(chapter_count):
        chapter_id = f"chapter-multi-{i}"
        chapter = Chapter(
            id=chapter_id,
            project_id=project.id,
            volume_id=volume.id,
            title=f"第{i+1}章",
            content=f"内容{i}",
            word_count=3,
            order=i + 1,
        )
        item = BackgroundJobItem(
            job_id=job.id,
            item_key=f"chapter:{chapter_id}",
            type="retrieval_chapter",
            status=JOB_STATUS_PENDING,
            payload_json=f'{{"project_id":"{project.id}","chapter_id":"{chapter_id}"}}',
            order_index=i,
        )
        state = RetrievalChapterIndexState(
            project_id=project.id,
            chapter_id=chapter_id,
            index_key=f"chapters:{project.id}",
            status="queued",
            source_hash="old",
            embedding_model_ref_id=model.id,
            job_id=job.id,
            item_id=item.id,
        )
        session.add(chapter)
        session.add(item)
        session.add(state)
        items.append(item)
        states.append(state)

    await session.commit()
    return job, items, states


@pytest.mark.asyncio
async def test_batch_emits_progress_per_sub_batch(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """多个章节应拆分为子批次，每批独立提交并推送进度。"""
    monkeypatch.setattr(definition, "MAX_EMBEDDING_CHUNKS_PER_REQUEST", 1)
    job, items, states = await _seed_multi_chapter_job(session, chapter_count=3)

    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: ChapterIndexIntegrationService(
            retrieval_service=MultiDocumentRetrievalService()
        ),
    )

    emit_count = 0

    async def _count_emit(_session, _project_id):
        nonlocal emit_count
        emit_count += 1

    monkeypatch.setattr(definition, "commit_and_emit_index_status", _count_emit)

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    result = await definition.handle_retrieval_chapter_index_batch(context)

    assert result == {"total": 3, "succeeded": 3, "failed": 0}
    assert emit_count == 3
    for state in states:
        await session.refresh(state)
        assert state.status == "ready"


class FailOnSecondBatchRetrievalService(MultiDocumentRetrievalService):
    """第二个子批次抛异常，验证出错即停止。"""

    def __init__(self) -> None:
        super().__init__()
        self._call_count = 0

    async def index_chunk_batch(self, session, index_key, chunks, embedding_client, **kwargs):
        self._call_count += 1
        if self._call_count == 2:
            raise RuntimeError("second batch failed")
        return await super().index_chunk_batch(
            session, index_key, chunks, embedding_client, **kwargs
        )


@pytest.mark.asyncio
async def test_batch_stops_on_error_and_marks_remaining_failed(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第二个子批次出错时，整个任务停止，剩余未处理章节统一标记为失败。"""
    monkeypatch.setattr(definition, "MAX_EMBEDDING_CHUNKS_PER_REQUEST", 1)
    job, items, states = await _seed_multi_chapter_job(session, chapter_count=3)

    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: ChapterIndexIntegrationService(
            retrieval_service=FailOnSecondBatchRetrievalService()
        ),
    )

    async def _noop_emit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(definition, "commit_and_emit_index_status", _noop_emit)

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await definition.handle_retrieval_chapter_index_batch(context)

    # 第一批成功(1)，第二批异常(1)，第三批未处理被标记失败(1)
    await session.refresh(items[0])
    await session.refresh(items[1])
    await session.refresh(items[2])
    assert items[0].status == JOB_STATUS_SUCCEEDED
    assert items[1].status == JOB_STATUS_FAILED
    assert items[2].status == JOB_STATUS_FAILED

    await session.refresh(states[0])
    await session.refresh(states[2])
    assert states[0].status == "ready"
    assert states[2].status == "failed"


class FailOneChapterRetrievalService(MultiDocumentRetrievalService):
    """首次 chunk 写入失败，验证任务会停止。"""

    async def index_chunk_batch(self, *args, **kwargs):
        raise RuntimeError("single chapter failed")


@pytest.mark.asyncio
async def test_batch_stops_on_partial_chapter_failure(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """单章索引失败时，整个任务停止，剩余未处理章节统一标记为失败。"""
    monkeypatch.setattr(definition, "MAX_EMBEDDING_CHUNKS_PER_REQUEST", 2)
    job, items, states = await _seed_multi_chapter_job(session, chapter_count=4)

    monkeypatch.setattr(
        definition,
        "_build_embedding_client",
        lambda session, model_ref_id: FakeEmbeddingClient(),
    )
    monkeypatch.setattr(
        definition,
        "ChapterIndexIntegrationService",
        lambda: ChapterIndexIntegrationService(
            retrieval_service=FailOneChapterRetrievalService()
        ),
    )

    async def _noop_emit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(definition, "commit_and_emit_index_status", _noop_emit)

    context = JobContext(
        session=session,
        job=job,
        publisher=BackgroundEventPublisher(),
    )
    context.check_cancelled = _noop_check_cancelled  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await definition.handle_retrieval_chapter_index_batch(context)

    # 首个请求失败后，所有章节均标记失败。
    await session.refresh(items[0])
    await session.refresh(items[1])
    await session.refresh(items[2])
    await session.refresh(items[3])
    assert items[0].status == JOB_STATUS_FAILED
    assert items[1].status == JOB_STATUS_FAILED
    assert items[2].status == JOB_STATUS_FAILED
    assert items[3].status == JOB_STATUS_FAILED
