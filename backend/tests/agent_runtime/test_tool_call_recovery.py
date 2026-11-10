import json

import pytest
from langchain_core.messages import AIMessage

from app.agent_runtime.tool_call_recovery import (
    TRUNCATED_TOOL_CALL_MESSAGE,
    is_malformed_tool_call,
    is_output_truncated,
    malformed_tool_call_failure,
    reconcile_tool_call_chunks,
    recover_message_tool_calls,
    tool_call_input,
)


@pytest.mark.parametrize(
    "metadata",
    [
        {"stop_reason": "max_tokens"},
        {"finish_reason": "length"},
        {"finish_reason": "MAX_TOKENS"},
    ],
)
def test_is_output_truncated_detects_provider_stop_reasons(metadata):
    assert is_output_truncated(AIMessage(content="", response_metadata=metadata))


@pytest.mark.parametrize(
    "metadata",
    [{}, {"stop_reason": "tool_use"}, {"finish_reason": "tool_calls"}],
)
def test_is_output_truncated_ignores_normal_stops(metadata):
    assert not is_output_truncated(AIMessage(content="", response_metadata=metadata))


def test_reconcile_tool_call_chunks_marks_truncated_args_instead_of_repairing():
    args_text = '{"note_ref": {"id": "n1"}, "old_content": "（待填充）", "new_content": "第一段'
    chunks = {0: {"id": "call_1", "name": "edit_note", "args_text": args_text}}

    repaired = reconcile_tool_call_chunks(chunks)
    truncated = reconcile_tool_call_chunks(chunks, truncated=True)

    assert not is_malformed_tool_call(repaired[0])
    assert is_malformed_tool_call(truncated[0])
    assert tool_call_input(truncated[0]) == args_text
    assert malformed_tool_call_failure(truncated[0]).message == (
        TRUNCATED_TOOL_CALL_MESSAGE
    )


def test_recover_message_tool_calls_marks_every_call_of_truncated_response():
    message = AIMessage(
        content="",
        tool_calls=[
            {"id": "call_1", "name": "read_note", "args": {"id": "n1"}},
            {"id": "call_2", "name": "edit_note", "args": {"old_content": "x"}},
        ],
        response_metadata={"stop_reason": "max_tokens"},
    )

    recovered = recover_message_tool_calls(message)

    assert [call["id"] for call in recovered] == ["call_1", "call_2"]
    assert all(is_malformed_tool_call(call) for call in recovered)
    assert json.loads(tool_call_input(recovered[1])) == {"old_content": "x"}


def test_recover_message_tool_calls_is_idempotent_for_truncated_response():
    message = AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": "edit_note", "args": {"old_content": "x"}}],
        response_metadata={"stop_reason": "max_tokens"},
    )
    first = recover_message_tool_calls(message)
    message.tool_calls = first  # type: ignore[assignment]

    second = recover_message_tool_calls(message)

    assert second == first


def test_malformed_tool_call_failure_keeps_default_message_for_parse_errors():
    recovered = reconcile_tool_call_chunks(
        {0: {"id": "call_1", "name": "edit_note", "args_text": "<<<<"}}
    )

    assert malformed_tool_call_failure(recovered[0]).message == (
        "工具参数 JSON 无法解析，未执行工具调用"
    )
