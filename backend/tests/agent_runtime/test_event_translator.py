from langchain_core.messages import ToolMessage
from langchain_core.messages.ai import AIMessage

from app.agent_runtime.runner.event_translator import EventTranslator


def single_event(result):
    assert isinstance(result, dict)
    return result


def test_translate_chat_model_stream():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_chat_model_stream",
        "data": {"chunk": type("Chunk", (), {"content": "Hello"})()},
        "name": "ChatOpenAI",
        "tags": [],
    }
    result = single_event(translator.translate(event))
    assert result is not None
    assert result["name"] == "agent:token"
    assert result["data"]["content"] == "Hello"
    assert result["data"]["session_id"] == "sess_001"


def test_translate_ignores_subagent_child_events():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_chat_model_stream",
        "data": {"chunk": type("Chunk", (), {"content": "child output"})()},
        "name": "ChatOpenAI",
        "tags": ["subagent_child"],
    }

    assert translator.translate(event) is None


def test_translate_subagent_child_events_when_opted_in():
    translator = EventTranslator(
        session_id="child_thread_001",
        allow_subagent_child_events=True,
    )
    event = {
        "event": "on_chat_model_stream",
        "run_id": "child-run-1",
        "data": {"chunk": type("Chunk", (), {"content": "child output"})()},
        "name": "ChatOpenAI",
        "tags": ["subagent_child"],
    }

    result = single_event(translator.translate(event))

    assert result["name"] == "agent:token"
    assert result["data"] == {
        "session_id": "child_thread_001",
        "run_id": "child-run-1",
        "content": "child output",
    }


def test_translate_ignores_subagent_child_write_chapter_tool_result():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_tool_end",
        "name": "write_chapter",
        "data": {
            "input": {"title": "第一章"},
            "output": {"success": True, "tool_name": "write_chapter"},
        },
        "tags": ["subagent_child"],
    }

    assert translator.translate(event) is None


def test_translate_chat_model_stream_reasoning_content():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_chat_model_stream",
        "data": {
            "chunk": type(
                "Chunk",
                (),
                {
                    "content": "",
                    "reasoning_content": "先分析需求",
                },
            )()
        },
        "name": "ChatOpenAI",
        "tags": [],
    }
    result = single_event(translator.translate(event))
    assert result is not None
    assert result["name"] == "agent:reasoning"
    assert result["data"]["content"] == "先分析需求"


def test_translate_chat_model_stream_reasoning_and_content():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_chat_model_stream",
        "data": {
            "chunk": type(
                "Chunk",
                (),
                {
                    "content": "结论",
                    "reasoning_content": "先分析需求",
                },
            )()
        },
        "name": "ChatOpenAI",
        "tags": [],
    }
    result = translator.translate(event)
    assert isinstance(result, list)
    assert [item["name"] for item in result] == ["agent:reasoning", "agent:token"]
    assert result[0]["data"]["content"] == "先分析需求"
    assert result[1]["data"]["content"] == "结论"


def test_translate_chat_model_stream_tool_call_chunks():
    translator = EventTranslator(session_id="sess_001")
    first = {
        "event": "on_chat_model_stream",
        "run_id": "run_1",
        "data": {
            "chunk": type(
                "Chunk",
                (),
                {
                    "content": "",
                    "tool_call_chunks": [
                        {
                            "index": 0,
                            "id": "call_1",
                            "name": "ask_user",
                            "args": '{"questions":',
                        }
                    ],
                },
            )()
        },
        "name": "ChatOpenAI",
        "tags": [],
    }
    second = {
        "event": "on_chat_model_stream",
        "run_id": "run_1",
        "data": {
            "chunk": type(
                "Chunk",
                (),
                {
                    "content": "",
                    "tool_call_chunks": [
                        {
                            "index": 0,
                            "id": None,
                            "name": None,
                            "args": "[]}",
                        }
                    ],
                },
            )()
        },
        "name": "ChatOpenAI",
        "tags": [],
    }

    first_result = single_event(translator.translate(first))
    second_result = single_event(translator.translate(second))

    assert first_result["name"] == "agent:tool_call"
    assert first_result["data"]["tool_call_id"] == "call_1"
    assert first_result["data"]["tool"] == "ask_user"
    assert first_result["data"]["partial_args"] == '{"questions":'
    assert first_result["data"]["args_text"] == '{"questions":'
    assert first_result["data"]["is_delta"] is True
    assert second_result["data"]["tool_call_id"] == "call_1"
    assert second_result["data"]["tool"] == "ask_user"
    assert second_result["data"]["partial_args"] == "[]}"
    assert second_result["data"]["args_text"] == '{"questions":[]}'
    assert second_result["data"]["is_delta"] is True


def test_translate_chat_model_stream_synthesizes_tool_call_id_without_model_id():
    translator = EventTranslator(session_id="sess_001")
    stream_event = {
        "event": "on_chat_model_stream",
        "run_id": "run_1",
        "data": {
            "chunk": type(
                "Chunk",
                (),
                {
                    "content": "",
                    "tool_call_chunks": [
                        {
                            "index": 0,
                            "id": None,
                            "name": "create_plan",
                            "args": "<<<<",
                        }
                    ],
                },
            )()
        },
        "name": "ChatOpenAI",
        "tags": [],
    }
    end_event = {
        "event": "on_chat_model_end",
        "run_id": "run_1",
        "data": {
            "output": AIMessage(
                content="",
                invalid_tool_calls=[
                    {
                        "name": "create_plan",
                        "args": "<<<<",
                        "error": "invalid json",
                        "type": "invalid_tool_call",
                    }
                ],
            )
        },
        "name": "ChatOpenAI",
        "tags": [],
    }

    stream_result = single_event(translator.translate(stream_event))
    end_result = single_event(translator.translate(end_event))

    assert stream_result["name"] == "agent:tool_call"
    synthesized_id = stream_result["data"]["tool_call_id"]
    assert isinstance(synthesized_id, str) and synthesized_id
    assert end_result["name"] == "agent:tool_result"
    assert end_result["data"]["tool_call_id"] == synthesized_id
    assert end_result["data"]["tool"] == "create_plan"
    assert end_result["data"]["input"] == "<<<<"
    assert end_result["data"]["output"]["reason"] == "malformed_tool_call"
    assert end_result["data"]["output"]["success"] is False


def test_translate_chat_model_stream_empty_content():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_chat_model_stream",
        "data": {"chunk": type("Chunk", (), {"content": ""})()},
        "name": "ChatOpenAI",
        "tags": [],
    }
    result = translator.translate(event)
    assert result is None


def test_translate_tool_start():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_tool_start",
        "name": "edit_chapter",
        "data": {"input": {"chapter_id": 1, "content": "new text"}},
        "metadata": {"tool_call_id": "call_edit_1"},
        "tags": [],
    }
    result = translator.translate(event)
    assert result is not None
    assert result["name"] == "agent:tool_call"
    assert result["data"]["tool"] == "edit_chapter"
    assert result["data"]["tool_call_id"] == "call_edit_1"
    assert result["data"]["input"] == {"chapter_id": 1, "content": "new text"}


def test_translate_tool_end():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_tool_end",
        "name": "edit_chapter",
        "data": {
            "input": {"chapter_id": 1},
            "output": "Chapter updated successfully",
        },
        "metadata": {"tool_call": {"id": "call_edit_1"}},
        "tags": [],
    }
    result = translator.translate(event)
    assert result is not None
    assert result["name"] == "agent:tool_result"
    assert result["data"]["tool_call_id"] == "call_edit_1"
    assert result["data"]["input"] == {"chapter_id": 1}
    assert result["data"]["output"] == "Chapter updated successfully"


def test_translate_tool_end_normalizes_tool_message_output():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_tool_end",
        "name": "ask_user",
        "data": {
            "input": {"questions": []},
            "output": ToolMessage(
                content='{"error":"参数校验失败"}',
                tool_call_id="call_1",
                name="ask_user",
                status="error",
            ),
        },
        "tags": [],
    }
    result = translator.translate(event)
    assert result is not None
    assert result["name"] == "agent:tool_result"
    assert result["data"]["output"] == {
        "content": '{"error":"参数校验失败"}',
        "tool_call_id": "call_1",
        "name": "ask_user",
        "status": "error",
    }
    assert result["data"]["tool_call_id"] == "call_1"


def test_translate_unknown_event_returns_none():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_chain_start",
        "name": "RunnableSequence",
        "data": {},
        "tags": [],
    }
    result = translator.translate(event)
    assert result is None


def test_translate_node_start_does_not_emit_deprecated_handoff():
    translator = EventTranslator(session_id="sess_001")
    event = {
        "event": "on_chain_start",
        "name": "writer",
        "data": {},
        "tags": ["graph:step:2", "agent_node"],
    }
    result = translator.translate(event)
    assert result is None


def test_translate_chat_model_end_usage():
    translator = EventTranslator(session_id="sess_001")
    output = type(
        "Output",
        (),
        {
            "usage_metadata": {
                "input_tokens": 12,
                "output_tokens": 34,
                "total_tokens": 46,
            }
        },
    )()
    event = {
        "event": "on_chat_model_end",
        "data": {"output": output},
        "name": "ChatOpenAI",
        "tags": [],
    }

    result = translator.translate(event)

    assert result is not None
    assert result["name"] == "agent:usage"
    assert result["data"] == {
        "session_id": "sess_001",
        "usage": {
            "input_tokens": 12,
            "output_tokens": 34,
            "total_tokens": 46,
        },
    }
