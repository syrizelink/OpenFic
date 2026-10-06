import json
from unittest.mock import patch

import httpx
import pytest
import respx
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_chunk_to_message,
)
from langchain_core.messages import ai as ai_messages
from langchain_core.tools import StructuredTool

from app.models.clients.openai_codex import OpenAICodexChatModel, OpenAICodexResponseError
from app.agent_runtime.context.processors.filter import filter_invalid
from app.agent_runtime.context.processors.to_langchain import to_langchain_messages
from app.agent_runtime.context.types import ContextMessage


def _stream(*events: dict) -> str:
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events)


def _model() -> OpenAICodexChatModel:
    return OpenAICodexChatModel(
        model="gpt-visible",
        api_key="access-token",
        provider_id=None,
    )


def test_openai_codex_raw_output_does_not_restore_filtered_orphan_tool_call():
    reasoning = {"type": "reasoning", "id": "rs_1", "summary": [],
                 "encrypted_content": "encrypted-state"}
    call_1 = {"type": "function_call", "call_id": "call_1", "name": "lookup", "arguments": "{}"}
    call_2 = {**call_1, "call_id": "call_2"}
    output = [reasoning, call_1, {**reasoning, "id": "rs_2"}, call_2]
    parts = filter_invalid([
        ContextMessage(
            role="assistant", content="", metadata={"part": "history"},
            tool_calls=[{"id": "call_1", "name": "lookup", "args": {}},
                        {"id": "call_2", "name": "lookup", "args": {}}],
            additional_kwargs={"responses_output": output},
        ),
        ContextMessage(role="tool", content="Found", tool_call_id="call_1",
                       metadata={"part": "history"}),
    ])
    messages = to_langchain_messages(parts)
    assert [call["id"] for call in messages[0].tool_calls] == ["call_1"]
    payload = _model()._build_payload(messages, None)
    assert payload["input"][:3] == output[:3]
    assert payload["input"][3:] == [
        {"type": "function_call_output", "call_id": "call_1", "output": "Found"},
    ]


@pytest.mark.asyncio
@respx.mock
async def test_openai_codex_sends_full_responses_input_and_supported_fields_only():
    route = respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(
            200,
            text=_stream(
                {"type": "response.output_text.delta", "delta": "Hello"},
                {
                    "type": "response.completed",
                    "response": {"id": "resp_1", "usage": {"input_tokens": 2, "output_tokens": 1}},
                },
            ),
        )
    )

    result = await _model().ainvoke(
        [
            SystemMessage(content="You are concise."),
            HumanMessage(content="Hi"),
            AIMessage(content="Previous answer"),
            ToolMessage(content="tool output", tool_call_id="call_1"),
        ]
    )

    payload = json.loads(route.calls[0].request.content)
    assert payload["store"] is False
    assert payload["stream"] is True
    assert payload["instructions"] == "You are concise."
    assert [item["role"] for item in payload["input"][:2]] == ["user", "assistant"]
    assert payload["input"][2]["type"] == "function_call_output"
    assert payload["include"] == ["reasoning.encrypted_content"]
    assert payload.keys() == {"model", "input", "instructions", "store", "stream", "include"}
    assert result.content == "Hello"
    assert type(result) is AIMessage


@pytest.mark.asyncio
@respx.mock
async def test_openai_codex_sends_function_tools_and_returns_tool_call_chunks():
    route = respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(
            200,
            text=_stream(
                {
                    "type": "response.output_item.added",
                    "item": {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "lookup"},
                },
                {
                    "type": "response.function_call_arguments.delta",
                    "item_id": "fc_1",
                    "delta": '{"query":',
                },
                {
                    "type": "response.function_call_arguments.delta",
                    "item_id": "fc_1",
                    "delta": '"OpenFic"}',
                },
                {"type": "response.completed", "response": {"id": "resp_2"}},
            ),
        )
    )
    tool = StructuredTool.from_function(
        lambda query: query,
        name="lookup",
        description="Look up data",
    )

    result = await _model().bind_tools([tool]).ainvoke([HumanMessage(content="Search")])

    payload = json.loads(route.calls[0].request.content)
    assert payload["tools"][0]["type"] == "namespace"
    assert payload["tools"][0]["name"] == "openfic"
    assert payload["tools"][0]["tools"] == [
        {
            "type": "function",
            "name": "lookup",
            "strict": False,
            "description": "Look up data",
            "parameters": {"properties": {"query": {}}, "required": ["query"], "type": "object"},
        }
    ]
    assert result.tool_calls[0]["id"] == "call_1"
    assert result.tool_calls[0]["name"] == "lookup"
    assert result.tool_calls[0]["args"] == {"query": "OpenFic"}
    assert len(result.tool_calls) == 1
    history = _model()._build_payload([result], None)
    assert history["input"][0]["namespace"] == "openfic"


@pytest.mark.asyncio
@pytest.mark.parametrize("output_source", ["completed", "done"])
@pytest.mark.parametrize("streaming", [False, True])
@respx.mock
async def test_openai_codex_replays_encrypted_reasoning_in_output_order(
    output_source: str, streaming: bool,
):
    reasoning = {
        "type": "reasoning", "id": "rs_1", "status": "completed",
        "summary": [{"type": "summary_text", "text": "Check context"}],
        "encrypted_content": "encrypted-state",
    }
    call = {
        "type": "function_call", "id": "fc_1", "call_id": "call_1",
        "name": "lookup", "namespace": "openfic", "arguments": '{"query":"OpenFic"}',
        "status": "completed",
    }
    second_reasoning = {**reasoning, "id": "rs_2", "encrypted_content": "second-state"}
    output = [reasoning, call, second_reasoning]
    events = [
        {"type": "response.reasoning_summary_text.delta", "delta": "Check "},
        {"type": "response.reasoning_summary_text.delta", "delta": "context"},
        {"type": "response.output_item.added", "output_index": 0,
         "item": {"type": "reasoning", "id": "rs_1", "summary": []}},
        {"type": "response.output_item.added", "output_index": 1, "item": call},
        {"type": "response.function_call_arguments.delta", "item_id": "fc_1", "delta": ""},
        {"type": "response.function_call_arguments.done", "item_id": "fc_1",
         "arguments": call["arguments"]},
        *[{"type": "response.output_item.done", "output_index": index, "item": item}
          for index, item in reversed(list(enumerate(output)))],
        {"type": "response.completed", "response": {
            "id": "resp_reasoning", **({"output": output} if output_source == "completed" else {}),
        }},
    ]
    route = respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(200, text=_stream(*events))
    )
    model = _model()
    if streaming:
        accumulated = None
        async for chunk in model.astream([HumanMessage(content="Search")]):
            accumulated = chunk if accumulated is None else accumulated + chunk
        assert accumulated is not None
        result = message_chunk_to_message(accumulated)
    else:
        result = await model.ainvoke([HumanMessage(content="Search")])
    assert result.additional_kwargs["responses_output"] == output
    assert result.additional_kwargs["reasoning_content"] == "Check context"
    assert result.tool_calls[0]["args"] == {"query": "OpenFic"}
    # Exercise the same JSON round trip used when restoring persisted messages.
    restored = AIMessage.model_validate_json(result.model_dump_json())
    await model.ainvoke([
        HumanMessage(content="Search"), restored,
        ToolMessage(content="Found", tool_call_id="call_1"),
    ])
    payload = json.loads(route.calls[1].request.content)
    assert payload["include"] == ["reasoning.encrypted_content"]
    assert payload["input"][1:4] == output
    assert payload["input"][4] == {
        "type": "function_call_output", "call_id": "call_1", "output": "Found",
    }


@pytest.mark.asyncio
@respx.mock
async def test_openai_codex_aggregates_large_tool_arguments_without_reparsing_prefixes():
    arguments = json.dumps({"query": "x" * 8192})
    events = [
        {"type": "response.output_item.added", "item": {
            "type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "lookup",
        }},
        *[{"type": "response.function_call_arguments.delta", "item_id": "fc_1",
           "delta": arguments[index:index + 64]} for index in range(0, len(arguments), 64)],
        {"type": "response.output_text.delta", "delta": "Found "},
        {"type": "response.output_text.delta", "delta": "context"},
        {"type": "response.reasoning_text.delta", "delta": "Think "},
        {"type": "response.reasoning_text.delta", "delta": "first"},
        {"type": "response.completed", "response": {
            "id": "resp_large", "usage": {"input_tokens": 3, "output_tokens": 5,
                "input_tokens_details": {"cached_tokens": 2}},
        }},
    ]
    respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(200, text=_stream(*events))
    )
    with patch.object(ai_messages, "parse_partial_json", wraps=ai_messages.parse_partial_json) as parser:
        result = await _model().ainvoke([HumanMessage(content="Search")])
    parsed_characters = sum(len(call.args[0]) for call in parser.call_args_list)
    assert parsed_characters <= 2 * len(arguments)
    assert result.content == "Found context"
    assert result.additional_kwargs["reasoning_content"] == "Think first"
    assert result.tool_calls == [{
        "name": "lookup", "id": "call_1", "args": {"query": "x" * 8192}, "type": "tool_call",
    }]
    assert result.usage_metadata == {
        "input_tokens": 3, "output_tokens": 5, "total_tokens": 8,
        "input_token_details": {"cache_read": 2},
    }
    assert result.response_metadata["response_id"] == "resp_large"
    assert result.response_metadata["finish_reason"] == "stop"


@pytest.mark.asyncio
@respx.mock
async def test_openai_codex_completed_only_tool_calls_keep_invalid_arguments():
    respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(200, text=_stream({
            "type": "response.completed", "response": {
                "id": "resp_tools", "output": [
                    {"type": "function_call", "call_id": "call_1", "name": "lookup",
                     "arguments": '{"query":"first"}'},
                    {"type": "function_call", "call_id": "call_2", "name": "lookup",
                     "arguments": "not-json"},
                ],
            },
        }))
    )
    result = await _model().ainvoke([HumanMessage(content="Search")])
    assert result.tool_calls == [{
        "id": "call_1", "name": "lookup", "args": {"query": "first"}, "type": "tool_call",
    }]
    assert result.invalid_tool_calls == [{
        "id": "call_2", "name": "lookup", "args": "not-json", "error": None,
        "type": "invalid_tool_call",
    }]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event",
    [
        {"type": "response.failed", "response": {"error": {"code": "failed"}}},
        {"type": "response.incomplete", "response": {"incomplete_details": {"reason": "max_output_tokens"}}},
    ],
)
@respx.mock
async def test_openai_codex_requires_response_completed(event: dict):
    respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(200, text=_stream(event))
    )

    with pytest.raises(OpenAICodexResponseError):
        await _model().ainvoke([HumanMessage(content="Hi")])


@pytest.mark.asyncio
@respx.mock
async def test_openai_codex_error_event_after_text_is_not_success():
    respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(200, text=_stream(
            {"type": "response.output_text.delta", "delta": "partial"},
            {"type": "error", "code": "subscription_sharing_usage_limit_exceeded"},
            {"type": "response.completed", "response": {"id": "resp_1"}},
        ))
    )
    with pytest.raises(OpenAICodexResponseError, match="subscription_sharing_usage_limit_exceeded"):
        await _model().ainvoke([HumanMessage(content="Hi")])
