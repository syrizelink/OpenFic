import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from tests.model_registry import register_sqlmodel_models

from app.core.ids import generate_id
from app.storage.models.commit import Commit
from app.storage.models.project import Project
from app.storage.models.revision import Revision
from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
from app.storage.models.revision_character_snapshot import RevisionCharacterSnapshot
from app.storage.models.revision_note_snapshot import (
    RevisionNoteCategorySnapshot,
    RevisionNoteSnapshot,
)
from app.storage.models.revision_world_entry_snapshot import RevisionWorldEntrySnapshot
from app.storage.models.task import Task
from app.storage.services.revision_service import cleanup_orphaned_revision_data


def _revision(revision_id: str, project_id: str, task_id: str | None = None) -> Revision:
    return Revision(
        id=revision_id,
        project_id=project_id,
        task_id=task_id,
        message="版本",
        revision_type="agent",
        status="completed",
        is_checkpoint=True,
        project_snapshot_title="标题",
    )


@pytest_asyncio.fixture
async def revision_cleanup_session():
    register_sqlmodel_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _count(session: AsyncSession, model) -> int:
    return int(
        (await session.execute(select(func.count()).select_from(model))).scalar_one()
    )


async def test_cleanup_removes_dangling_children_and_orphan_revisions(
    revision_cleanup_session: AsyncSession,
):
    session = revision_cleanup_session

    session.add(Project(id="proj-live", title="存活项目"))
    session.add(
        Task(
            id="task-live",
            project_id="proj-live",
            title="存活任务",
            mode="agent",
            agent_session_id="sess-live",
        )
    )
    # dangling children: revision ids that do not exist
    session.add(Commit(id=generate_id(), revision_id="rev-missing", chapter_id="c1", operation="update"))
    session.add(RevisionChapterSnapshot(id=generate_id(), revision_id="rev-missing", chapter_id="c1", project_id="proj-live"))
    session.add(RevisionNoteSnapshot(id=generate_id(), revision_id="rev-missing", note_id="n1", project_id="proj-live"))
    session.add(RevisionNoteCategorySnapshot(id=generate_id(), revision_id="rev-missing", category_id="cat1", project_id="proj-live"))
    session.add(RevisionCharacterSnapshot(id=generate_id(), revision_id="rev-missing", character_id="char1", project_id="proj-live"))
    session.add(RevisionWorldEntrySnapshot(id=generate_id(), revision_id="rev-missing", entry_id="e1", project_id="proj-live"))
    # orphan revision whose project is gone
    session.add(_revision("rev-project-gone", "proj-gone"))
    session.add(Commit(id=generate_id(), revision_id="rev-project-gone", chapter_id="c1", operation="update"))
    session.add(RevisionChapterSnapshot(id=generate_id(), revision_id="rev-project-gone", chapter_id="c1", project_id="proj-gone"))
    # orphan revision whose task is gone (project still exists)
    session.add(_revision("rev-task-gone", "proj-live", task_id="task-gone"))
    session.add(Commit(id=generate_id(), revision_id="rev-task-gone", chapter_id="c1", operation="update"))
    await session.commit()

    deleted = await cleanup_orphaned_revision_data(session)
    await session.commit()

    # 6 dangling children + 2 orphan revisions + 3 children of orphan revisions
    assert deleted == 6 + 2 + 3
    assert await _count(session, Commit) == 0
    assert await _count(session, RevisionChapterSnapshot) == 0
    assert await _count(session, RevisionNoteSnapshot) == 0
    assert await _count(session, RevisionNoteCategorySnapshot) == 0
    assert await _count(session, RevisionCharacterSnapshot) == 0
    assert await _count(session, RevisionWorldEntrySnapshot) == 0
    assert await _count(session, Revision) == 0


async def test_cleanup_preserves_valid_revision_history(
    revision_cleanup_session: AsyncSession,
):
    session = revision_cleanup_session
    session.add(Project(id="proj-live", title="存活项目"))
    session.add(
        Task(
            id="task-live",
            project_id="proj-live",
            title="存活任务",
            mode="agent",
            agent_session_id="sess-live",
        )
    )
    session.add(_revision("rev-live", "proj-live", task_id="task-live"))
    session.add(Commit(id=generate_id(), revision_id="rev-live", chapter_id="c1", operation="update"))
    session.add(RevisionChapterSnapshot(id=generate_id(), revision_id="rev-live", chapter_id="c1", project_id="proj-live"))
    await session.commit()

    deleted = await cleanup_orphaned_revision_data(session)
    await session.commit()

    assert deleted == 0
    assert await _count(session, Revision) == 1
    assert await _count(session, Commit) == 1
    assert await _count(session, RevisionChapterSnapshot) == 1
