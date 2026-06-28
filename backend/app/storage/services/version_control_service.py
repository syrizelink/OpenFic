"""Shared project-stat helper for versioned agent writes."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.models.project import Project
from app.storage.repos import chapter_repo, project_repo


async def refresh_project_stats(session: AsyncSession, project_id: str) -> Project:
    """Recompute cached project chapter and word counts in the caller transaction."""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    project.chapter_count = await chapter_repo.count_by_project(session, project_id)
    project.word_count = await chapter_repo.get_total_word_count(session, project_id)
    project.updated_at = datetime.now(UTC)
    await project_repo.update(session, project)
    return project
