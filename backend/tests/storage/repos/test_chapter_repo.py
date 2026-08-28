# -*- coding: utf-8 -*-
"""chapter_repo 仓储层测试。"""

import pytest
from sqlalchemy import inspect

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


@pytest.mark.asyncio
async def test_list_metadata_by_project_does_not_load_content(session):
    project = Project(title="P", description="")
    volume = Volume(project_id=project.id, title="第一卷", order=1)
    chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="C1",
        content="正文不应被读取",
        word_count=8,
        order=1,
    )
    session.add(project)
    session.add(volume)
    session.add(chapter)
    await session.commit()
    session.sync_session.expunge_all()

    chapters = await chapter_repo.list_metadata_by_project(session, project.id)

    assert len(chapters) == 1
    assert chapters[0].title == "C1"
    assert "content" in inspect(chapters[0]).unloaded


@pytest.mark.asyncio
async def test_list_metadata_by_volume_does_not_load_content(session):
    project = Project(title="P", description="")
    volume = Volume(project_id=project.id, title="第一卷", order=1)
    chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="C1",
        content="正文不应被读取",
        word_count=8,
        order=1,
    )
    session.add(project)
    session.add(volume)
    session.add(chapter)
    await session.commit()
    session.sync_session.expunge_all()

    chapters = await chapter_repo.list_metadata_by_volume(
        session, volume.id, offset=0, limit=1
    )

    assert len(chapters) == 1
    assert chapters[0].title == "C1"
    assert "content" in inspect(chapters[0]).unloaded


@pytest.mark.asyncio
async def test_get_by_volume_ref_supports_order_and_first_matching_title(session):
    project = Project(title="P", description="")
    volume = Volume(project_id=project.id, title="第一卷", order=1)
    first = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="相同标题",
        content="第一章正文",
        order=1,
    )
    second = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="相同标题",
        content="第二章正文",
        order=2,
    )
    session.add(project)
    session.add(volume)
    session.add(first)
    session.add(second)
    await session.commit()

    by_order = await chapter_repo.get_by_volume_ref(
        session, volume.id, ref_type="order", ref_value=2
    )
    by_title = await chapter_repo.get_by_volume_ref(
        session, volume.id, ref_type="title", ref_value="相同标题"
    )

    assert by_order is not None
    assert by_order.id == second.id
    assert by_title is not None
    assert by_title.id == first.id
