# -*- coding: utf-8 -*-

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.chapter.summary_generator import (
    build_chapter_summary_prompt,
    build_long_term_summary_prompt,
)
from app.storage.models.chapter import Chapter
from app.storage.models.chapter_summary import ChapterSummary
from app.storage.models.project import Project
from app.storage.models.volume import Volume
@pytest.mark.asyncio
async def test_build_chapter_summary_prompt_includes_previous_chapter_and_target(
    session: AsyncSession,
) -> None:
    project = Project(title="项目", description="")
    session.add(project)
    await session.flush()
    volume = Volume(project_id=project.id, title="第一卷", order=1, chapter_count=2)
    session.add(volume)
    await session.flush()
    previous_chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="第一章",
        content="上一章原文",
        order=1,
    )
    target_chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="第二章",
        content="本章原文",
        order=2,
    )
    session.add_all([previous_chapter, target_chapter])
    await session.flush()
    session.add(
        ChapterSummary(
            project_id=project.id,
            summary_type="chapter",
            status="ready",
            chapter_id=previous_chapter.id,
            volume_id=volume.id,
            chapter_order=1,
            start_time="地球历 2026-01-01 00:00",
            characters_json='["张三"]',
            locations_json='["京城"]',
        )
    )
    await session.flush()

    prompt = await build_chapter_summary_prompt(session, target_chapter.id)

    assert len(prompt.messages) >= 3
    assert any("emit_chapter_summary" in message.content for message in prompt.messages)
    assert prompt.messages[-2].content == (
        "以下部分是上一个章节的有关内容，用以帮助你连贯的理解剧情信息，该部分与你要总结的内容**无关**。\n"
        "<previous_chapter>\n"
        "  <title>第一章</title>\n"
        "  <start_time>地球历 2026-01-01 00:00</start_time>\n"
        "  <characters>[\"张三\"]</characters>\n"
        "  <locations>[\"京城\"]</locations>\n"
        "  <content>上一章原文</content>\n"
        "</previous_chapter>"
    )
    assert prompt.messages[-1].content == (
        "以下部分是你需要总结的章节内容。\n"
        "<target_chapter>\n"
        "  <title>第二章</title>\n"
        "  <content>本章原文</content>\n"
        "</target_chapter>"
    )
    assert all("{{getmem" not in message.content for message in prompt.messages)
    assert all("{{getworld}}" not in message.content for message in prompt.messages)


@pytest.mark.asyncio
async def test_build_chapter_summary_prompt_omits_previous_chapter_part_for_first_volume_chapter(
    session: AsyncSession,
) -> None:
    project = Project(title="项目", description="")
    session.add(project)
    await session.flush()
    previous_volume = Volume(project_id=project.id, title="第一卷", order=1, chapter_count=1)
    target_volume = Volume(project_id=project.id, title="第二卷", order=2, chapter_count=1)
    session.add_all([previous_volume, target_volume])
    await session.flush()
    session.add(
        Chapter(
            project_id=project.id,
            volume_id=previous_volume.id,
            title="上一卷第一章",
            content="不应注入的原文",
            order=1,
        )
    )
    chapter = Chapter(
        project_id=project.id,
        volume_id=target_volume.id,
        title="第一章",
        content="本章原文",
        order=1,
    )
    session.add(chapter)
    await session.flush()

    prompt = await build_chapter_summary_prompt(session, chapter.id)

    assert all("<previous_chapter>" not in message.content for message in prompt.messages)
    assert prompt.messages[-1].content == (
        "以下部分是你需要总结的章节内容。\n"
        "<target_chapter>\n"
        "  <title>第一章</title>\n"
        "  <content>本章原文</content>\n"
        "</target_chapter>"
    )


@pytest.mark.asyncio
async def test_build_long_term_summary_prompt_omits_default_context(session: AsyncSession) -> None:
    project = Project(title="项目", description="")
    session.add(project)
    await session.flush()
    volume = Volume(project_id=project.id, title="第一卷", order=1, chapter_count=1)
    session.add(volume)
    await session.flush()
    chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="第一章",
        content="章节原文",
        order=1,
    )
    session.add(chapter)
    await session.flush()
    summary = ChapterSummary(
        project_id=project.id,
        summary_type="chapter",
        status="ready",
        chapter_id=chapter.id,
        volume_id=volume.id,
        chapter_order=1,
        summary="章节摘要",
    )

    prompt = await build_long_term_summary_prompt(session, [summary], [chapter])

    assert any("emit_long_term_summary" in message.content for message in prompt.messages)
    assert prompt.messages[-1].content == (
        "以下部分是你需要总结的摘要内容\n"
        "<target_summaries>\n"
        "  <sum1>\n"
        "    <title>第一章</title>\n"
        "    <content>章节摘要</content>\n"
        "  </sum1>\n"
        "</target_summaries>"
    )
    assert all("{{getmem" not in message.content for message in prompt.messages)
    assert all("{{getworld}}" not in message.content for message in prompt.messages)
