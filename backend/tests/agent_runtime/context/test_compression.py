import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.processors.compress import (
    SETTING_KEY_COMPRESS_SYSTEM_PROMPTS,
    compress_system_prompts,
    compress_system_prompts_if_enabled,
    is_compress_system_prompts_enabled,
    merge_consecutive_system_dicts,
    merge_consecutive_system_messages,
)
from app.agent_runtime.context.types import ContextMessage


def test_merges_consecutive_system_messages() -> None:
    messages = [
        ContextMessage(role="system", content="A", metadata={"part": "system_prompt"}),
        ContextMessage(role="system", content="B", metadata={"part": "system_prompt"}),
        ContextMessage(role="system", content="C", metadata={"part": "system_prompt"}),
    ]

    merged = compress_system_prompts(messages)

    assert len(merged) == 1
    assert merged[0].role == "system"
    assert merged[0].content == "A\n\nB\n\nC"
    assert merged[0].metadata == {"part": "system_prompt"}


def test_keeps_non_consecutive_system_messages() -> None:
    messages = [
        ContextMessage(role="system", content="A", metadata={"part": "system_prompt"}),
        ContextMessage(role="user", content="mid", metadata={"part": "system_prompt"}),
        ContextMessage(role="system", content="B", metadata={"part": "system_prompt"}),
    ]

    merged = compress_system_prompts(messages)

    assert [m.content for m in merged] == ["A", "mid", "B"]


def test_preserves_first_message_metadata() -> None:
    messages = [
        ContextMessage(
            role="system",
            content="A",
            name="prompt-a",
            tool_call_id="call-a",
            metadata={"part": "system_prompt"},
            attachments=[{"type": "image_url", "image_url": {"url": "x"}}],
        ),
        ContextMessage(role="system", content="B", metadata={"part": "rules"}),
    ]

    merged = compress_system_prompts(messages)

    assert len(merged) == 1
    assert merged[0].name == "prompt-a"
    assert merged[0].tool_call_id == "call-a"
    assert merged[0].metadata == {"part": "system_prompt"}
    assert merged[0].attachments == [{"type": "image_url", "image_url": {"url": "x"}}]


def test_returns_original_list_when_no_consecutive_system_messages() -> None:
    messages = [
        ContextMessage(role="user", content="u"),
        ContextMessage(role="system", content="s"),
        ContextMessage(role="assistant", content="a"),
    ]

    merged = compress_system_prompts(messages)

    assert merged == messages


@pytest.mark.asyncio
async def test_if_enabled_merges_when_setting_true() -> None:
    messages = [
        ContextMessage(role="system", content="A", metadata={"part": "system_prompt"}),
        ContextMessage(role="system", content="B", metadata={"part": "system_prompt"}),
    ]

    with patch(
        "app.agent_runtime.context.processors.compress.setting_repo.get_by_key",
        new=AsyncMock(
            return_value=SimpleNamespace(key=SETTING_KEY_COMPRESS_SYSTEM_PROMPTS, value="true")
        ),
    ):
        merged = await compress_system_prompts_if_enabled(messages, AsyncMock())

    assert [m.content for m in merged] == ["A\n\nB"]


@pytest.mark.asyncio
async def test_if_enabled_keeps_original_when_setting_missing() -> None:
    messages = [
        ContextMessage(role="system", content="A", metadata={"part": "system_prompt"}),
        ContextMessage(role="system", content="B", metadata={"part": "system_prompt"}),
    ]

    with patch(
        "app.agent_runtime.context.processors.compress.setting_repo.get_by_key",
        new=AsyncMock(return_value=None),
    ):
        merged = await compress_system_prompts_if_enabled(messages, AsyncMock())

    assert merged is messages


@pytest.mark.asyncio
async def test_if_enabled_keeps_original_when_setting_false() -> None:
    messages = [
        ContextMessage(role="system", content="A", metadata={"part": "system_prompt"}),
        ContextMessage(role="system", content="B", metadata={"part": "system_prompt"}),
    ]

    with patch(
        "app.agent_runtime.context.processors.compress.setting_repo.get_by_key",
        new=AsyncMock(
            return_value=SimpleNamespace(key=SETTING_KEY_COMPRESS_SYSTEM_PROMPTS, value="false")
        ),
    ):
        merged = await compress_system_prompts_if_enabled(messages, AsyncMock())

    assert merged is messages


@pytest.mark.asyncio
async def test_if_enabled_wraps_setting_load_errors() -> None:
    cause = RuntimeError("boom")

    with patch(
        "app.agent_runtime.context.processors.compress.setting_repo.get_by_key",
        new=AsyncMock(side_effect=cause),
    ):
        with pytest.raises(ContextBuildError) as exc:
            await compress_system_prompts_if_enabled([], AsyncMock())

    assert exc.value.part == "settings"
    assert exc.value.cause is cause


@pytest.mark.asyncio
async def test_is_enabled_parses_values() -> None:
    async def setting_value(value: str | None):
        with patch(
            "app.agent_runtime.context.processors.compress.setting_repo.get_by_key",
            new=AsyncMock(
                return_value=(
                    SimpleNamespace(key=SETTING_KEY_COMPRESS_SYSTEM_PROMPTS, value=value)
                    if value is not None
                    else None
                )
            ),
        ):
            return await is_compress_system_prompts_enabled(AsyncMock())

    assert await setting_value("true") is True
    assert await setting_value("false") is False
    assert await setting_value("") is False
    assert await setting_value(None) is False


def test_merge_consecutive_system_dicts() -> None:
    messages = [
        {"role": "system", "content": "A"},
        {"role": "system", "content": "B"},
        {"role": "user", "content": "u"},
        {"role": "system", "content": "C"},
    ]

    merged = merge_consecutive_system_dicts(messages)

    assert merged == [
        {"role": "system", "content": "A\n\nB"},
        {"role": "user", "content": "u"},
        {"role": "system", "content": "C"},
    ]


def test_merge_consecutive_system_dicts_preserves_extra_fields() -> None:
    messages = [
        {"role": "system", "content": "A", "name": "prompt-a"},
        {"role": "system", "content": "B"},
    ]

    merged = merge_consecutive_system_dicts(messages)

    assert merged == [{"role": "system", "content": "A\n\nB", "name": "prompt-a"}]


def test_merge_consecutive_system_messages() -> None:
    messages = [
        SystemMessage(content="A"),
        SystemMessage(content="B"),
        HumanMessage(content="u"),
        SystemMessage(content="C"),
    ]

    merged = merge_consecutive_system_messages(messages)

    assert [type(m).__name__ for m in merged] == [
        "SystemMessage",
        "HumanMessage",
        "SystemMessage",
    ]
    assert merged[0].content == "A\n\nB"
    assert merged[2].content == "C"
