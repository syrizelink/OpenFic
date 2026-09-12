# -*- coding: utf-8 -*-

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
    project = Project(title="Proyek", description="")
    session.add(project)
    await session.flush()
    volume = Volume(project_id=project.id, title="Volume 1", order=1, chapter_count=2)
    session.add(volume)
    await session.flush()
    previous_chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Bab 1",
        content="Teks asli bab sebelumnya",
        order=1,
    )
    target_chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Bab 2",
        content="Teks asli bab ini",
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
            start_time="Kalender Bumi 2026-01-01 00:00",
            characters_json='["Adi"]',
            locations_json='["Ibu Kota"]',
        )
    )
    await session.flush()

    prompt = await build_chapter_summary_prompt(session, target_chapter.id)

    assert len(prompt.messages) >= 3
    assert any("emit_chapter_summary" in message.content for message in prompt.messages)
    assert prompt.messages[-2].content == (
        "Bagian berikut adalah isi terkait dari bab sebelumnya, untuk membantumu memahami"
        " informasi alur cerita secara berkesinambungan; bagian ini **tidak berkaitan**"
        " dengan isi yang harus kamu ringkas.\n"
        "<previous_chapter>\n"
        "  <title>Bab 1</title>\n"
        "  <start_time>Kalender Bumi 2026-01-01 00:00</start_time>\n"
        "  <characters>[\"Adi\"]</characters>\n"
        "  <locations>[\"Ibu Kota\"]</locations>\n"
        "  <content>Teks asli bab sebelumnya</content>\n"
        "</previous_chapter>"
    )
    assert prompt.messages[-1].content == (
        "Bagian berikut adalah isi bab yang harus kamu ringkas.\n"
        "<target_chapter>\n"
        "  <title>Bab 2</title>\n"
        "  <content>Teks asli bab ini</content>\n"
        "</target_chapter>"
    )
    assert all("{{getmem" not in message.content for message in prompt.messages)
    assert all("{{getworld}}" not in message.content for message in prompt.messages)


@pytest.mark.asyncio
async def test_build_chapter_summary_prompt_omits_previous_chapter_part_for_first_volume_chapter(
    session: AsyncSession,
) -> None:
    project = Project(title="Proyek", description="")
    session.add(project)
    await session.flush()
    previous_volume = Volume(project_id=project.id, title="Volume 1", order=1, chapter_count=1)
    target_volume = Volume(project_id=project.id, title="Volume 2", order=2, chapter_count=1)
    session.add_all([previous_volume, target_volume])
    await session.flush()
    session.add(
        Chapter(
            project_id=project.id,
            volume_id=previous_volume.id,
            title="Volume Sebelumnya Bab 1",
            content="Teks asli yang tidak boleh disuntikkan",
            order=1,
        )
    )
    chapter = Chapter(
        project_id=project.id,
        volume_id=target_volume.id,
        title="Bab 1",
        content="Teks asli bab ini",
        order=1,
    )
    session.add(chapter)
    await session.flush()

    prompt = await build_chapter_summary_prompt(session, chapter.id)

    assert all("<previous_chapter>" not in message.content for message in prompt.messages)
    assert prompt.messages[-1].content == (
        "Bagian berikut adalah isi bab yang harus kamu ringkas.\n"
        "<target_chapter>\n"
        "  <title>Bab 1</title>\n"
        "  <content>Teks asli bab ini</content>\n"
        "</target_chapter>"
    )


@pytest.mark.asyncio
async def test_build_long_term_summary_prompt_omits_default_context(session: AsyncSession) -> None:
    project = Project(title="Proyek", description="")
    session.add(project)
    await session.flush()
    volume = Volume(project_id=project.id, title="Volume 1", order=1, chapter_count=1)
    session.add(volume)
    await session.flush()
    chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Bab 1",
        content="Teks asli bab",
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
        summary="Ringkasan bab",
    )

    prompt = await build_long_term_summary_prompt(session, [summary], [chapter])

    assert any("emit_long_term_summary" in message.content for message in prompt.messages)
    assert prompt.messages[-1].content == (
        "Bagian berikut adalah isi ringkasan yang harus kamu ringkas\n"
        "<target_summaries>\n"
        "  <sum1>\n"
        "    <title>Bab 1</title>\n"
        "    <content>Ringkasan bab</content>\n"
        "  </sum1>\n"
        "</target_summaries>"
    )
    assert all("{{getmem" not in message.content for message in prompt.messages)
    assert all("{{getworld}}" not in message.content for message in prompt.messages)


@pytest.mark.asyncio
async def test_build_chapter_summary_prompt_merges_system_messages_when_enabled(
    session: AsyncSession,
) -> None:
    project = Project(title="Proyek", description="")
    session.add(project)
    await session.flush()
    volume = Volume(project_id=project.id, title="Volume 1", order=1, chapter_count=2)
    session.add(volume)
    await session.flush()
    previous_chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Bab 1",
        content="Teks asli bab sebelumnya",
        order=1,
    )
    target_chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Bab 2",
        content="Teks asli bab ini",
        order=2,
    )
    session.add_all([previous_chapter, target_chapter])
    await session.flush()

    with patch(
        "app.agent_runtime.context.processors.compress.setting_repo.get_by_key",
        new=AsyncMock(
            return_value=SimpleNamespace(key="compress_system_prompts", value="true")
        ),
    ):
        prompt = await build_chapter_summary_prompt(session, target_chapter.id)

    assert len(prompt.messages) == 1
    assert "<previous_chapter>" in prompt.messages[0].content
    assert "<target_chapter>" in prompt.messages[0].content


@pytest.mark.asyncio
async def test_build_long_term_summary_prompt_merges_system_messages_when_enabled(
    session: AsyncSession,
) -> None:
    project = Project(title="Proyek", description="")
    session.add(project)
    await session.flush()
    volume = Volume(project_id=project.id, title="Volume 1", order=1, chapter_count=1)
    session.add(volume)
    await session.flush()
    chapter = Chapter(
        project_id=project.id,
        volume_id=volume.id,
        title="Bab 1",
        content="Teks asli bab",
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
        summary="Ringkasan bab",
    )

    with patch(
        "app.agent_runtime.context.processors.compress.setting_repo.get_by_key",
        new=AsyncMock(
            return_value=SimpleNamespace(key="compress_system_prompts", value="true")
        ),
    ):
        prompt = await build_long_term_summary_prompt(session, [summary], [chapter])

    assert len(prompt.messages) == 1
    assert "<target_summaries>" in prompt.messages[0].content
