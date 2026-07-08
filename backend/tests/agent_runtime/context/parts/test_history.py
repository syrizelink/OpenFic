import json
from unittest.mock import AsyncMock, patch
import pytest

from app.agent_runtime.context.parts.history import build_history

pytestmark = pytest.mark.asyncio


async def test_history_empty_returns_empty_list():
    assert await build_history([]) == []


async def test_history_maps_basic_fields():
    raw = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "在"},
    ]
    result = await build_history(raw)
    assert len(result) == 2
    assert result[0].role == "user"
    assert result[0].content == "你好"
    assert result[0].metadata == {"part": "history"}
    assert result[1].role == "assistant"


async def test_history_filters_non_message_and_hidden_records_first():
    raw = [
        {
            "role": "system",
            "content": "",
            "message_type": "node_start",
            "display_channel": "hidden",
        },
        {
            "role": "system",
            "content": "内部状态",
            "message_type": "message",
            "display_channel": "hidden",
        },
        {"role": "user", "content": "你好", "message_type": "message"},
        {"role": "assistant", "content": "在"},
    ]

    result = await build_history(raw)

    assert [message.role for message in result] == ["user", "assistant"]
    assert [message.content for message in result] == ["你好", "在"]


async def test_history_preserves_tool_call_id_for_tool_role():
    raw = [{"role": "tool", "content": "{}", "tool_call_id": "call_abc"}]
    result = await build_history(raw)
    assert result[0].role == "tool"
    assert result[0].tool_call_id == "call_abc"


async def test_history_compacts_chapter_write_tool_result_for_llm_context():
    raw = [{
        "role": "tool",
        "name": "write_chapter",
        "content": json.dumps(
            {
                "type": "ok",
                "success": True,
                "tool_name": "write_chapter",
                "revision_id": "rev-1",
                "word_count": 2,
                "chapter": {"id": "chap-1", "title": "第一章", "content": "正文"},
                "chapter_diff": {"operation": "create", "sections": []},
                "affected_chapters": ["chap-1"],
                "message": "章节已写入",
            },
            ensure_ascii=False,
        ),
        "tool_call_id": "call_abc",
    }]
    result = await build_history(raw)
    assert result[0].role == "tool"
    assert json.loads(result[0].content) == {
        "success": True,
        "tool_name": "write_chapter",
        "word_count": 2,
        "message": "章节已写入",
    }


async def test_history_preserves_tool_calls_for_assistant():
    raw = [{
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": "call_1", "name": "read_chapter", "args": {}}],
    }]
    result = await build_history(raw)
    assert result[0].role == "assistant"
    assert result[0].tool_calls == [{"id": "call_1", "name": "read_chapter", "args": {}}]


async def test_history_preserves_additional_kwargs_for_assistant():
    raw = [{
        "role": "assistant",
        "content": "",
        "additional_kwargs": {"reasoning_content": "先分析"},
    }]
    result = await build_history(raw)
    assert result[0].role == "assistant"
    assert result[0].additional_kwargs == {"reasoning_content": "先分析"}


async def test_history_preserves_extra_metadata_kind():
    raw = [{"role": "assistant", "content": "thinking", "kind": "thinking"}]
    result = await build_history(raw)
    assert result[0].metadata == {"part": "history", "kind": "thinking"}


async def test_history_compiles_user_mentions_for_llm_context_when_session_available():
    raw = [{
        "role": "user",
        "content": '<of-mention chapter_id="chap_1" label="旧章节" />',
    }]

    fake_session = object()
    with patch(
        "app.agent_runtime.context.parts.history.compile_canonical_mentions",
        AsyncMock(return_value=" @chapter:第一卷/第一章 "),
    ) as compile_mock:
        result = await build_history(raw, fake_session)

    compile_mock.assert_awaited_once_with(raw[0]["content"], fake_session)
    assert result[0].content == " @chapter:第一卷/第一章 "


async def test_history_preserves_user_xml_when_session_unavailable():
    raw = [{
        "role": "user",
        "content": '<of-mention chapter_id="chap_1" label="旧章节" />',
    }]

    result = await build_history(raw)

    assert result[0].content == raw[0]["content"]
