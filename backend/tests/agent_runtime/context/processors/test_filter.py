from typing import Literal

from app.agent_runtime.context.processors.filter import (
    filter_invalid,
    filter_tool_result_metadata_content,
)
from app.agent_runtime.context.types import ContextMessage

ContextRole = Literal["system", "user", "assistant", "tool"]


def _h(role: ContextRole, content: str = "", **meta) -> ContextMessage:
    metadata = {"part": "history"}
    metadata.update(meta)
    return ContextMessage(role=role, content=content, metadata=metadata)


def test_keeps_static_parts_unchanged() -> None:
    parts = [
        ContextMessage(role="system", content="", metadata={"part": "environment"}),
        ContextMessage(role="system", content="rules", metadata={"part": "rules"}),
    ]
    out = filter_invalid(parts)
    assert out == parts


def test_drops_empty_history_messages() -> None:
    parts = [
        _h("user", ""),
        _h("user", "   "),
        _h("user", "real"),
    ]
    out = filter_invalid(parts)
    assert len(out) == 1
    assert out[0].content == "real"


def test_drops_thinking_kind() -> None:
    parts = [
        _h("assistant", "thought", kind="thinking"),
        _h("assistant", "reply"),
    ]
    out = filter_invalid(parts)
    assert [m.content for m in out] == ["reply"]


def test_drops_orphan_tool_calls_pair() -> None:
    parts = [
        _h("assistant", "calling", **{}),
    ]
    parts[0].tool_calls = [{"id": "c1", "name": "x", "args": {}}]
    out = filter_invalid(parts)
    assert out == []


def test_keeps_paired_tool_call_and_response() -> None:
    asst = _h("assistant", "calling")
    asst.tool_calls = [{"id": "c1", "name": "x", "args": {}}]
    tool = _h("tool", "result")
    tool.tool_call_id = "c1"
    out = filter_invalid([asst, tool])
    assert len(out) == 2


def test_keeps_paired_empty_assistant_tool_call_and_response() -> None:
    asst = _h("assistant", "")
    asst.tool_calls = [{"id": "c1", "name": "x", "args": {}}]
    tool = _h("tool", "result")
    tool.tool_call_id = "c1"
    out = filter_invalid([asst, tool])
    assert len(out) == 2


def test_drops_orphan_tool_response_when_assistant_dropped() -> None:
    asst = _h("assistant", "thought", kind="thinking")
    asst.tool_calls = [{"id": "c1", "name": "x", "args": {}}]
    tool = _h("tool", "result")
    tool.tool_call_id = "c1"
    out = filter_invalid([asst, tool])
    assert out == []


def test_tool_result_metadata_content_keeps_success_result() -> None:
    content = '{"success":true,"metadata":{"note_diff":{"note_id":"note-1"}}}'

    assert filter_tool_result_metadata_content(content) == '{"success": true}'
