# -*- coding: utf-8 -*-
"""Chapter retrieval integration service tests."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.retrieval.chapter_index import (
    ChapterIndexIntegrationService,
    chapter_document_id,
    chapter_index_key,
    compute_chapter_source_hash,
)
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.retrieval_chapter_index_state import RetrievalChapterIndexState
from app.storage.models.volume import Volume


class RecordingRetrievalService:
    def __init__(self, *, fail_delete: bool = False) -> None:
        self.fail_delete = fail_delete
        self.deleted: list[tuple[str, str]] = []

    async def delete_document(self, session, index_key: str, document_id: str) -> None:
        _ = session
        self.deleted.append((index_key, document_id))
        if self.fail_delete:
            raise RuntimeError("delete failed")


def _chapter(project_id: str = "project-1") -> Chapter:
    return Chapter(
        id="chapter-1",
        project_id=project_id,
        volume_id="volume-1",
        title="第一章",
        content="英雄遇见龙",
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
    # text 保持为原始正文，前缀仅在分块/索引阶段注入，不污染回传内容。
    assert document.text == "英雄遇见龙"
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
        "chapter_title": "第一章",
        "prefix": "第1章 第一章",
        "source_hash": expected_hash,
    }


@pytest.mark.asyncio
async def test_mark_chapter_stale_if_content_hash_changed(session: AsyncSession) -> None:
    project = Project(id="project-1", title="项目", description="")
    volume = Volume(id="volume-1", project_id=project.id, title="第一卷", order=1)
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
            source_hash=compute_chapter_source_hash("旧正文"),
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
    assert state.source_hash == compute_chapter_source_hash("旧正文")


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
