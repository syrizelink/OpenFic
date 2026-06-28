from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from app.models.clients.llm_client import LLMClient, _patch_deepseek_reasoning_payload


def test_patch_deepseek_reasoning_payload_adds_reasoning_content() -> None:
    messages = [
        HumanMessage(content="use tool"),
        AIMessage(
            content="",
            additional_kwargs={"reasoning_content": "need chapter content"},
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "read_chapter",
                    "args": {"chapter_ref": {"type": "order", "value": 1}},
                }
            ],
        ),
    ]
    payload: dict[str, Any] = {
        "messages": [
            {"role": "user", "content": "use tool"},
            {"role": "assistant", "content": None, "tool_calls": []},
        ]
    }

    _patch_deepseek_reasoning_payload(messages, payload)

    assert payload["messages"][1]["reasoning_content"] == "need chapter content"


def test_extract_usage_prefers_usage_metadata() -> None:
    chunk = AIMessageChunk(
        content="hello",
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 2,
            "total_tokens": 12,
        },
        response_metadata={"token_usage": {"prompt_tokens": 1}},
    )

    assert LLMClient._extract_usage(chunk) == {
        "input_tokens": 10,
        "output_tokens": 2,
        "total_tokens": 12,
    }


def test_extract_usage_reads_response_metadata() -> None:
    message = AIMessage(
        content="hello",
        response_metadata={
            "token_usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
            }
        },
    )

    assert LLMClient._extract_usage(message) == {
        "prompt_tokens": 10,
        "completion_tokens": 2,
        "total_tokens": 12,
    }
