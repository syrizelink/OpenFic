"""Insert normalized imported documents into an existing project."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.editor_content_limits import validate_editor_content
from app.core.errors import NotFoundError
from app.core.txt_parser import ParsedVolume
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.volume import Volume
from app.storage.repos import project_repo, volume_repo
from app.storage.services import writing_activity_service

ImportPlacement = Literal["append", "after_volume"]


@dataclass
class ProjectChapterImportResult:
    first_chapter_id: str
    created_volume_ids: list[str]
    chapter_count: int
    total_word_count: int


async def resolve_placement(
    session: AsyncSession,
    project_id: str,
    placement: ImportPlacement,
    after_volume_id: str | None,
) -> tuple[Project, int]:
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")
    if placement == "append":
        return project, await volume_repo.get_max_order(session, project_id) + 1
    if placement != "after_volume" or not after_volume_id:
        raise ValueError("插入到指定卷之后时必须提供卷 ID")
    volume = await volume_repo.get_by_id(session, after_volume_id)
    if volume is None or volume.project_id != project_id:
        raise ValueError("指定的卷不存在或不属于当前项目")
    return project, volume.order + 1


async def import_documents(
    session: AsyncSession,
    project_id: str,
    volumes: list[ParsedVolume],
    *,
    placement: ImportPlacement = "append",
    after_volume_id: str | None = None,
) -> ProjectChapterImportResult:
    """Flush the full insertion; the caller owns the transaction boundary."""
    project, start_order = await resolve_placement(
        session, project_id, placement, after_volume_id
    )
    if not volumes or not any(volume.chapters for volume in volumes):
        raise ValueError("未能识别任何章节")
    await volume_repo.make_order_gap(session, project_id, start_order, len(volumes))
    created_volume_ids: list[str] = []
    chapters: list[Chapter] = []
    for order, parsed_volume in enumerate(volumes, start=start_order):
        volume = Volume(
            project_id=project_id,
            title=parsed_volume.title,
            order=order,
            chapter_count=len(parsed_volume.chapters),
        )
        await volume_repo.create(session, volume)
        created_volume_ids.append(volume.id)
        for chapter_order, parsed_chapter in enumerate(parsed_volume.chapters, start=1):
            validate_editor_content(parsed_chapter.content)
            chapter = Chapter(
                project_id=project_id,
                volume_id=volume.id,
                title=parsed_chapter.title,
                content=parsed_chapter.content,
                word_count=parsed_chapter.word_count,
                order=chapter_order,
            )
            session.add(chapter)
            await session.flush()
            chapters.append(chapter)
            await writing_activity_service.record_activity(
                session,
                project_id=project_id,
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                source="import",
                operation="import",
                old_word_count=0,
                new_word_count=chapter.word_count,
            )
    total_word_count = sum(chapter.word_count for chapter in chapters)
    project.chapter_count += len(chapters)
    project.word_count += total_word_count
    project.updated_at = datetime.now(UTC)
    await session.flush()

    # Keep batch imports aligned with normal chapter creation: enqueue at the
    # project level once, then let the caller commit and publish notifications.
    from app.retrieval.chapter_index import safe_maybe_enqueue_auto_index

    await safe_maybe_enqueue_auto_index(session, project_id=project_id)

    return ProjectChapterImportResult(
        first_chapter_id=chapters[0].id,
        created_volume_ids=created_volume_ids,
        chapter_count=len(chapters),
        total_word_count=total_word_count,
    )
