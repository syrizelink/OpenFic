import json

import httpx
import pytest
import respx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from app.models.clients.openai_codex import OpenAICodexChatModel, OpenAICodexResponseError


def _stream(*events: dict) -> str:
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events)


def _model() -> OpenAICodexChatModel:
    return OpenAICodexChatModel(
        model="gpt-visible",
        api_key="access-token",
        provider_id=None,
    )


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
    assert payload.keys() == {"model", "input", "instructions", "store", "stream"}
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
