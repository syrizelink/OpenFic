# -*- coding: utf-8 -*-
"""chapter_repo 仓储层测试。"""

import pytest

from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.volume import Volume
from app.storage.repos import chapter_repo


@pytest.mark.asyncio
async def test_get_by_project_and_order_returns_chapter(session):
    project = Project(title="P", description="")
    session.add(project)
    await session.flush()

    volume = Volume(project_id=project.id, title="第一卷", order=1, chapter_count=1)
    session.add(volume)
    await session.flush()

    chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="C1",
        order=1,
        word_count=0,
    )
    session.add(chapter)
    await session.flush()

    result = await chapter_repo.get_by_project_and_order(session, project.id, 1)
    assert result is not None
    assert result.id == chapter.id


@pytest.mark.asyncio
async def test_get_by_project_and_order_returns_none_when_missing(session):
    project = Project(title="P", description="")
    session.add(project)
    await session.flush()

    result = await chapter_repo.get_by_project_and_order(session, project.id, 99)
    assert result is None


@pytest.mark.asyncio
async def test_get_by_project_and_order_uses_volume_ordered_flat_index(session):
    project = Project(title="P", description="")
    session.add(project)
    await session.flush()

    first_volume = Volume(
        project_id=project.id,
        title="第一卷",
        order=1,
        chapter_count=1,
    )
    second_volume = Volume(
        project_id=project.id,
        title="第二卷",
        order=2,
        chapter_count=1,
    )
    session.add(first_volume)
    session.add(second_volume)
    await session.flush()

    first_chapter = Chapter(
        project_id=project.id,
        volume_id=first_volume.id,
        title="第一卷第一章",
        order=1,
        word_count=0,
    )
    second_chapter = Chapter(
        project_id=project.id,
        volume_id=second_volume.id,
        title="第二卷第一章",
        order=1,
        word_count=0,
    )
    session.add(first_chapter)
    session.add(second_chapter)
    await session.flush()

    result = await chapter_repo.get_by_project_and_order(session, project.id, 2)

    assert result is not None
    assert result.id == second_chapter.id
