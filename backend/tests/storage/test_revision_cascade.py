import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from tests.model_registry import register_sqlmodel_models

from app.core.ids import generate_id
from app.storage.models.commit import Commit
from app.storage.models.project import Project
from app.storage.models.revision import Revision
from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
from app.storage.models.revision_content_blob import RevisionContentBlob
from app.storage.models.task import Task
from app.storage.repos import revision_content_blob_repo
from app.storage.services.revision_service import (
    delete_revision_data_by_project,
    delete_revision_data_by_tasks,
)


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
async def cascade_session():
    register_sqlmodel_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _blob_count(session: AsyncSession) -> int:
    return int(
        (await session.execute(select(RevisionContentBlob))).scalars().all().__len__()
    )


async def _seed_two_revisions(session: AsyncSession):
    long_shared = "这是共享的一段很长正文。" * 200
    long_exclusive = "这是独占的一段很长正文。" * 200

    shared_blob = await revision_content_blob_repo.put(session, long_shared)
    exclusive_blob = await revision_content_blob_repo.put(session, long_exclusive)
    await session.commit()

    session.add(Project(id="proj-1", title="项目一"))
    session.add(Project(id="proj-2", title="项目二"))
    session.add(
        Task(id="task-1", project_id="proj-1", title="任务一", mode="agent", agent_session_id="sess-1")
    )
    session.add(
        Task(id="task-2", project_id="proj-2", title="任务二", mode="agent", agent_session_id="sess-2")
    )
    session.add(_revision("rev-1", "proj-1", task_id="task-1"))
    session.add(_revision("rev-2", "proj-2", task_id="task-2"))

    session.add(
        Commit(
            id=generate_id(),
            revision_id="rev-1",
            chapter_id="c1",
            operation="update",
            snapshot_content_blob_id=shared_blob,
            new_content_blob_id=exclusive_blob,
        )
    )
    session.add(
        Commit(
            id=generate_id(),
            revision_id="rev-2",
            chapter_id="c1",
            operation="update",
            snapshot_content_blob_id=shared_blob,
        )
    )
    session.add(
        RevisionChapterSnapshot(
            id=generate_id(),
            revision_id="rev-1",
            chapter_id="c1",
            project_id="proj-1",
            exists=True,
            content_blob_id=shared_blob,
        )
    )
    await session.commit()


async def test_delete_revision_data_by_project_cascades_and_gc_blobs(
    cascade_session: AsyncSession,
):
    session = cascade_session
    await _seed_two_revisions(session)
    assert await _blob_count(session) == 2

    await delete_revision_data_by_project(session, "proj-1")
    await session.commit()

    # rev-1 + its commit + chapter snapshot removed; exclusive blob removed.
    assert await session.get(Revision, "rev-1") is None
    assert (await session.execute(select(Commit).where(Commit.revision_id == "rev-1"))).first() is None
    assert (await session.execute(select(RevisionChapterSnapshot).where(RevisionChapterSnapshot.revision_id == "rev-1"))).first() is None
    assert await _blob_count(session) == 1

    # rev-2 survives, and shared blob is still referenced by its commit.
    assert await session.get(Revision, "rev-2") is not None
    remaining = (await session.execute(select(RevisionContentBlob))).scalars().all()
    assert remaining[0].id != ""


async def test_delete_revision_data_by_tasks_gc_blobs_when_last_reference_removed(
    cascade_session: AsyncSession,
):
    session = cascade_session
    await _seed_two_revisions(session)

    # Removing task-2 keeps rev-1's references, so both blobs survive.
    await delete_revision_data_by_tasks(session, ["task-2"])
    await session.commit()
    assert await session.get(Revision, "rev-2") is None
    assert await session.get(Revision, "rev-1") is not None
    assert await _blob_count(session) == 2

    # Removing task-1 removes the last references, so both blobs are collected.
    await delete_revision_data_by_tasks(session, ["task-1"])
    await session.commit()
    assert await session.get(Revision, "rev-1") is None
    assert await _blob_count(session) == 0
