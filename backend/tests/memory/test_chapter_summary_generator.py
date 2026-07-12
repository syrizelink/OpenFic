# -*- coding: utf-8 -*-

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.chapter.summary_generator import _build_prompt_messages


@pytest.mark.asyncio
async def test_build_prompt_messages_appends_target_xml(
    session: AsyncSession,
) -> None:
    messages = await _build_prompt_messages(
        session,
        task_name="mid_range_summary",
        target_xml="<target><chapter_title>第一章</chapter_title></target>",
    )

    assert messages[0].content
    assert any("emit_chapter_summary" in message.content for message in messages)
    assert "<target><chapter_title>第一章</chapter_title></target>" == messages[-1].content
    assert all("{{chapter_title}}" not in message.content for message in messages)
    assert all("{{chapter_content}}" not in message.content for message in messages)
