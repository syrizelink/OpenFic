# -*- coding: utf-8 -*-
"""Chapter retrieval integration service tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.retrieval import chapter_index
from app.retrieval.chapter_index import (
    ChapterIndexIntegrationService,
    ChapterIndexSource,
    INDEX_MODE_ALL,
    INDEX_MODE_OFF,
    IndexSettingsConfig,
    chapter_document_id,
    chapter_index_key,
    compute_chapter_source_hash,
    compute_project_index_status,
)
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.retrieval_chapter_index_state import RetrievalChapterIndexState
from app.storage.models.volume import Volume


class RecordingRetrievalService:
    def __init__(
        self, *, fail_delete: bool = False, fail_drop: bool = False
    ) -> None:
        self.fail_delete = fail_delete
        self.fail_drop = fail_drop
        self.deleted: list[tuple[str, str]] = []
        self.dropped: list[str] = []

    async def delete_document(self, session, index_key: str, document_id: str) -> None:
        _ = session
        self.deleted.append((index_key, document_id))
        if self.fail_delete:
            raise RuntimeError("delete failed")

    async def drop_index(self, session, index_key: str) -> bool:
        _ = session
        self.dropped.append(index_key)
        if self.fail_drop:
            raise RuntimeError("drop failed")
        return True


def _chapter(project_id: str = "project-1") -> Chapter:
    return Chapter(
        id="chapter-1",
        project_id=project_id,
        volume_id="volume-1",
        title="Bab 1",
        content="Pahlawan berjumpa naga",
        word_count=5,
        order=1,
    )


@pytest.mark.asyncio
async def test_chapter_document_contains_stable_ids_and_metadata() -> None:
    chapter = _chapter()
    service = ChapterIndexIntegrationService(retrieval_service=RecordingRetrievalService())

    document = service.build_chapter_document(chapter)

    expected_hash = compute_chapter_source_hash(chapter.content)
    assert chapter_index_key(chapter.project_id) == "chapters:project-1"
    assert chapter_document_id(chapter.id) == "chapter:chapter-1"
    assert document.document_id == "chapter:chapter-1"
    # text tetap berisi isi utama asli; prefiks hanya disuntikkan pada tahap chunking/indexing
    # sehingga tidak mengotori isi yang dikembalikan.
    assert document.text == "Pahlawan berjumpa naga"
    assert document.attributes == {
        "project_id": "project-1",
        "chapter_id": "chapter-1",
        "volume_id": "volume-1",
    }
    assert document.metadata == {
        "source_type": "chapter",
        "project_id": "project-1",
        "chapter_id": "chapter-1",
        "volume_id": "volume-1",
        "chapter_order": 1,
        "chapter_title": "Bab 1",
        # Prefiks dibentuk oleh app (_build_chapter_prefix) dengan pola CJK bawaan aplikasi,
        # jadi bagian "第1章" dipertahankan apa adanya.
        "prefix": "第1章 Bab 1",
        "source_hash": expected_hash,
    }


@pytest.mark.asyncio
async def test_mark_chapter_stale_if_content_hash_changed(session: AsyncSession) -> None:
    project = Project(id="project-1", title="Proyek", description="")
    volume = Volume(id="volume-1", project_id=project.id, title="Volume 1", order=1)
    chapter = _chapter(project.id)
    session.add(project)
    session.add(volume)
    session.add(chapter)
    session.add(
        RetrievalChapterIndexState(
            project_id=project.id,
            chapter_id=chapter.id,
            index_key=chapter_index_key(project.id),
            status="ready",
            source_hash=compute_chapter_source_hash("Isi utama lama"),
            embedding_model_ref_id="model-1",
            chunk_count=2,
        )
    )
    await session.commit()

    await ChapterIndexIntegrationService().mark_chapter_stale_if_changed(session, chapter)

    state = (
        await session.execute(
            select(RetrievalChapterIndexState).where(
                col(RetrievalChapterIndexState.chapter_id) == chapter.id
            )
        )
    ).scalar_one()
    assert state.status == "stale"
    assert state.source_hash == compute_chapter_source_hash("Isi utama lama")


@pytest.mark.asyncio
async def test_disabled_project_index_status_does_not_load_chapter_content(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_sources = AsyncMock(side_effect=AssertionError("Kueri isi utama tidak boleh dipanggil"))
    count_chapters = AsyncMock(return_value=3)
    resolve_model = AsyncMock(side_effect=AssertionError("Model tidak boleh di-resolve saat fitur nonaktif"))
    monkeypatch.setattr(chapter_index.chapter_repo, "list_index_source_by_project", list_sources)
    monkeypatch.setattr(chapter_index.chapter_repo, "count_by_project", count_chapters)
    monkeypatch.setattr(chapter_index, "resolve_index_embedding_model", resolve_model)

    config = IndexSettingsConfig(
        mode=INDEX_MODE_OFF,
        enabled_projects=set(),
        chunk_size=800,
        chunk_overlap=100,
        auto_strategy="off",
        embedding_model_ref_id="",
        rerank_enabled=False,
        rerank_model_ref_id="",
    )

    status = await compute_project_index_status(
        session,
        project_id="project-1",
        title="Proyek",
        config=config,
        model=None,
    )

    assert status.total_chapters == 3
    assert status.status == "disabled"
    list_sources.assert_not_awaited()
    count_chapters.assert_awaited_once_with(session, "project-1")
    resolve_model.assert_not_awaited()


@pytest.mark.asyncio
async def test_enqueue_project_index_update_uses_lightweight_chapter_sources(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = IndexSettingsConfig(
        mode=INDEX_MODE_ALL,
        enabled_projects=set(),
        chunk_size=800,
        chunk_overlap=100,
        auto_strategy="immediate",
        embedding_model_ref_id="model-1",
        rerank_enabled=False,
        rerank_model_ref_id="",
    )
    model = SimpleNamespace(id="model-1", dimensions=3)
    list_sources = AsyncMock(
        return_value=[ChapterIndexSource("project-1", "chapter-1", "Isi utama")]
    )
    list_chapters = AsyncMock(side_effect=AssertionError("Bab lengkap tidak boleh dimuat"))
    monkeypatch.setattr(chapter_index, "get_index_settings", AsyncMock(return_value=config))
    monkeypatch.setattr(chapter_index, "resolve_index_embedding_model", AsyncMock(return_value=model))
    monkeypatch.setattr(chapter_index.chapter_repo, "list_index_source_by_project", list_sources)
    monkeypatch.setattr(chapter_index.chapter_repo, "list_by_project", list_chapters)
    monkeypatch.setattr(
        chapter_index.retrieval_index_repo,
        "get_by_index_key",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        chapter_index.retrieval_chapter_index_state_repo,
        "list_by_project",
        AsyncMock(return_value=[]),
    )
    integration = SimpleNamespace(ensure_project_index=AsyncMock())
    monkeypatch.setattr(chapter_index, "ChapterIndexIntegrationService", lambda: integration)
    monkeypatch.setattr(
        "app.background.jobs.service.submit_job",
        AsyncMock(return_value=SimpleNamespace(id="job-1")),
    )
    monkeypatch.setattr(
        "app.background.jobs.service.create_items",
        AsyncMock(return_value=[SimpleNamespace(id="item-1")]),
    )
    queue_chapters = AsyncMock()
    monkeypatch.setattr(
        chapter_index.retrieval_chapter_index_state_repo,
        "queue_chapters_for_job",
        queue_chapters,
    )

    result = await chapter_index.enqueue_project_index_update(
        session,
        project_id="project-1",
    )

    assert result is not None
    assert result.enqueued_count == 1
    list_sources.assert_awaited_once_with(session, "project-1")
    list_chapters.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_chapter_index_removes_state_and_best_effort_deletes_document(
    session: AsyncSession,
) -> None:
    chapter = _chapter()
    retrieval_service = RecordingRetrievalService(fail_delete=True)
    session.add(
        RetrievalChapterIndexState(
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            index_key=chapter_index_key(chapter.project_id),
            status="ready",
            source_hash=compute_chapter_source_hash(chapter.content),
            embedding_model_ref_id="model-1",
        )
    )
    await session.commit()

    await ChapterIndexIntegrationService(
        retrieval_service=retrieval_service
    ).delete_chapter_index(session, chapter)

    state = (
        await session.execute(
            select(RetrievalChapterIndexState).where(
                col(RetrievalChapterIndexState.chapter_id) == chapter.id
            )
        )
    ).scalar_one_or_none()
    assert state is None
    assert retrieval_service.deleted == [
        (chapter_index_key(chapter.project_id), chapter_document_id(chapter.id))
    ]


@pytest.mark.asyncio
async def test_mark_chapter_stale_if_indexed_marks_ready_state_without_content_change(
    session: AsyncSession,
) -> None:
    chapter = _chapter()
    state = RetrievalChapterIndexState(
        project_id=chapter.project_id,
        chapter_id=chapter.id,
        index_key=chapter_index_key(chapter.project_id),
        status="ready",
        source_hash=compute_chapter_source_hash(chapter.content),
        embedding_model_ref_id="model-1",
        chunk_count=2,
    )
    session.add(state)
    await session.commit()

    await ChapterIndexIntegrationService().mark_chapter_stale_if_indexed(
        session,
        chapter,
    )

    await session.refresh(state)
    assert state.status == "stale"


@pytest.mark.asyncio
async def test_delete_project_index_removes_all_project_states_and_drops_index(
    session: AsyncSession,
) -> None:
    retrieval_service = RecordingRetrievalService()
    other_project_id = "project-2"
    session.add_all(
        [
            RetrievalChapterIndexState(
                project_id="project-1",
                chapter_id="chapter-1",
                index_key=chapter_index_key("project-1"),
                status="ready",
                source_hash="hash-1",
                embedding_model_ref_id="model-1",
            ),
            RetrievalChapterIndexState(
                project_id="project-1",
                chapter_id="chapter-2",
                index_key=chapter_index_key("project-1"),
                status="stale",
                source_hash="hash-2",
                embedding_model_ref_id="model-1",
            ),
            # Kontrak indeks lama pada proyek yang sama juga harus terbuang.
            RetrievalChapterIndexState(
                project_id="project-1",
                chapter_id="chapter-3",
                index_key="chapters:project-1:legacy",
                status="ready",
                source_hash="hash-3",
                embedding_model_ref_id="model-0",
            ),
            # Proyek lain wajib tidak tersentuh.
            RetrievalChapterIndexState(
                project_id=other_project_id,
                chapter_id="chapter-9",
                index_key=chapter_index_key(other_project_id),
                status="ready",
                source_hash="hash-9",
                embedding_model_ref_id="model-1",
            ),
        ]
    )
    await session.commit()

    await ChapterIndexIntegrationService(
        retrieval_service=retrieval_service
    ).delete_project_index(session, "project-1")

    remaining = (
        (
            await session.execute(
                select(RetrievalChapterIndexState).where(
                    col(RetrievalChapterIndexState.project_id) == "project-1"
                )
            )
        )
        .scalars()
        .all()
    )
    assert list(remaining) == []
    assert retrieval_service.dropped == [chapter_index_key("project-1")]

    survivor = (
        await session.execute(
            select(RetrievalChapterIndexState).where(
                col(RetrievalChapterIndexState.project_id) == other_project_id
            )
        )
    ).scalar_one()
    assert survivor.chapter_id == "chapter-9"


@pytest.mark.asyncio
async def test_delete_project_index_survives_drop_failure(
    session: AsyncSession,
) -> None:
    """Kegagalan membuang berkas indeks tidak boleh menggagalkan hapus proyek."""
    retrieval_service = RecordingRetrievalService(fail_drop=True)
    session.add(
        RetrievalChapterIndexState(
            project_id="project-1",
            chapter_id="chapter-1",
            index_key=chapter_index_key("project-1"),
            status="ready",
            source_hash="hash-1",
            embedding_model_ref_id="model-1",
        )
    )
    await session.commit()

    await ChapterIndexIntegrationService(
        retrieval_service=retrieval_service
    ).delete_project_index(session, "project-1")

    remaining = (
        (
            await session.execute(
                select(RetrievalChapterIndexState).where(
                    col(RetrievalChapterIndexState.project_id) == "project-1"
                )
            )
        )
        .scalars()
        .all()
    )
    assert list(remaining) == []
    assert retrieval_service.dropped == [chapter_index_key("project-1")]
