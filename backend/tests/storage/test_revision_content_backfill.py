import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from tests.model_registry import register_sqlmodel_models

from app.core.ids import generate_id
from app.storage.models.commit import Commit
from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
from app.storage.models.revision_character_snapshot import RevisionCharacterSnapshot
from app.storage.models.revision_content_blob import RevisionContentBlob
from app.storage.repos import (
    commit_repo,
    revision_chapter_snapshot_repo,
)
from app.storage.services.revision_content_backfill import backfill_revision_content_blobs


@pytest_asyncio.fixture
async def revision_backfill_session():
    register_sqlmodel_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with factory() as session:
        yield session


async def test_backfill_rewrites_long_text_and_dedupes(
    revision_backfill_session: AsyncSession,
):
    session = revision_backfill_session
    long_shared = "这是很长的一段正文内容。" * 200
    long_after = long_shared + "另一段不同的结尾。"
    short = "短内容"

    session.add(
        Commit(
            id=generate_id(),
            revision_id="rev-1",
            chapter_id="chap-1",
            operation="update",
            snapshot_content=long_shared,
            new_content=long_after,
        )
    )
    session.add(
        Commit(
            id=generate_id(),
            revision_id="rev-1",
            chapter_id="chap-2",
            operation="update",
            snapshot_content=short,
            new_content=None,
        )
    )
    session.add(
        RevisionChapterSnapshot(
            id=generate_id(),
            revision_id="rev-1",
            chapter_id="chap-1",
            project_id="proj-1",
            exists=True,
            content=long_shared,
        )
    )
    session.add(
        RevisionCharacterSnapshot(
            id=generate_id(),
            revision_id="rev-1",
            character_id="char-1",
            project_id="proj-1",
            exists=True,
            description=long_shared,
        )
    )
    await session.commit()

    calls: list[tuple[float | None, int, int]] = []
    rewritten = await backfill_revision_content_blobs(
        session,
        progress_callback=lambda _phase, progress, done, total: calls.append(
            (progress, done, total)
        ),
    )

    assert rewritten == 4
    assert calls[0][0] is None
    assert calls[-1][0] == 1.0

    blobs = (await session.execute(select(RevisionContentBlob))).scalars().all()
    assert len(blobs) == 2

    raw = (
        await session.execute(
            text(
                "SELECT snapshot_content, snapshot_content_blob_id "
                "FROM commits WHERE chapter_id = 'chap-1'"
            )
        )
    ).fetchone()
    assert raw[0] is None and raw[1]

    raw_short = (
        await session.execute(
            text(
                "SELECT snapshot_content, snapshot_content_blob_id "
                "FROM commits WHERE chapter_id = 'chap-2'"
            )
        )
    ).fetchone()
    assert raw_short[0] == short and raw_short[1] is None

    chapter_snapshots = await revision_chapter_snapshot_repo.list_by_revision(
        session, "rev-1"
    )
    assert len(chapter_snapshots) == 1
    assert chapter_snapshots[0].content == long_shared

    commits = await commit_repo.list_by_revision(session, "rev-1")
    by_chapter = {commit.chapter_id: commit for commit in commits}
    assert by_chapter["chap-1"].snapshot_content == long_shared
    assert by_chapter["chap-1"].new_content == long_after
    assert by_chapter["chap-2"].snapshot_content == short
    assert by_chapter["chap-2"].new_content is None


async def test_backfill_is_idempotent(revision_backfill_session: AsyncSession):
    session = revision_backfill_session
    long = "这是很长的一段正文内容。" * 200
    session.add(
        RevisionChapterSnapshot(
            id=generate_id(),
            revision_id="rev-1",
            chapter_id="chap-1",
            project_id="proj-1",
            exists=True,
            content=long,
        )
    )
    await session.commit()

    assert await backfill_revision_content_blobs(session) == 1
    assert await backfill_revision_content_blobs(session) == 0
