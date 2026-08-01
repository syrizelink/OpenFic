import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.processors.to_langchain import to_langchain_messages
from app.agent_runtime.context.types import ContextMessage


def _accept_langchain_human_content(content: str | list[str | dict[object, object]]) -> None:
    pass


def test_system_message_mapped() -> None:
    parts = [ContextMessage(role="system", content="rules")]
    out = to_langchain_messages(parts)
    assert len(out) == 1
    assert isinstance(out[0], SystemMessage)
    assert out[0].content == "rules"


def test_user_message_mapped_to_human() -> None:
    parts = [ContextMessage(role="user", content="hello")]
    out = to_langchain_messages(parts)
    assert isinstance(out[0], HumanMessage)
    assert out[0].content == "hello"


def test_user_message_with_image_attachments_mapped_to_multimodal_content() -> None:
    parts = [
        ContextMessage(
            role="user",
            content="描述这张图",
            attachments=[
                {
                    "type": "image",
                    "mime_type": "image/png",
                    "base64": "aW1hZ2U=",
                }
            ],
        )
    ]

    out = to_langchain_messages(parts)

    assert isinstance(out[0], HumanMessage)
    assert out[0].content == [
        {"type": "text", "text": "描述这张图"},
        {"type": "image", "base64": "aW1hZ2U=", "mime_type": "image/png"},
    ]


def test_multimodal_content_matches_langchain_human_message_contract() -> None:
    content: list[str | dict[object, object]] = [
        {"type": "text", "text": "描述这张图"},
        {"type": "image", "base64": "aW1hZ2U=", "mime_type": "image/png"},
    ]

    _accept_langchain_human_content(content)


def test_user_message_with_only_image_attachments_has_no_empty_text_block() -> None:
    out = to_langchain_messages(
        [
            ContextMessage(
                role="user",
                content="",
                attachments=[
                    {"type": "image", "base64": "aW1hZ2U=", "mime_type": "image/png"}
                ],
            )
        ]
    )

    assert isinstance(out[0], HumanMessage)
    assert out[0].content == [
        {"type": "image", "base64": "aW1hZ2U=", "mime_type": "image/png"}
    ]


def test_assistant_message_mapped_to_ai_with_tool_calls() -> None:
    parts = [
        ContextMessage(
            role="assistant",
            content="",
            tool_calls=[{"id": "call_1", "name": "read_chapter", "args": {"order": 1}}],
        )
    ]
    out = to_langchain_messages(parts)
    assert isinstance(out[0], AIMessage)
    assert len(out[0].tool_calls) == 1
    tc = out[0].tool_calls[0]
    assert tc["id"] == "call_1"
    assert tc["name"] == "read_chapter"
    assert tc["args"] == {"order": 1}


def test_assistant_message_without_tool_calls() -> None:
    parts = [ContextMessage(role="assistant", content="reply")]
    out = to_langchain_messages(parts)
    assert isinstance(out[0], AIMessage)
    assert out[0].content == "reply"
    assert out[0].tool_calls == []


def test_assistant_message_preserves_reasoning_content() -> None:
    parts = [
        ContextMessage(
            role="assistant",
            content="",
            additional_kwargs={"reasoning_content": "先分析"},
        )
    ]
    out = to_langchain_messages(parts)
    assert isinstance(out[0], AIMessage)
    assert out[0].additional_kwargs["reasoning_content"] == "先分析"


def test_tool_message_mapped_with_tool_call_id() -> None:
    parts = [
        ContextMessage(
            role="tool", content="ok", tool_call_id="call_1"
        )
    ]
    out = to_langchain_messages(parts)
    assert isinstance(out[0], ToolMessage)
    assert out[0].tool_call_id == "call_1"
    assert out[0].content == "ok"


def test_tool_message_missing_tool_call_id_raises() -> None:
    parts = [ContextMessage(role="tool", content="ok")]
    with pytest.raises(ContextBuildError) as exc:
        to_langchain_messages(parts)
    assert exc.value.part == "to_langchain"


def test_unknown_role_raises() -> None:
    parts = [ContextMessage(role="weird", content="x")]  # type: ignore[arg-type]
    with pytest.raises(ContextBuildError) as exc:
        to_langchain_messages(parts)
    assert exc.value.part == "to_langchain"
