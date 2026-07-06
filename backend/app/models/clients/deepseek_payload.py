# -*- coding: utf-8 -*-
"""Shared DeepSeek payload helpers."""

from typing import Any, cast

from langchain_core.messages import AIMessage


def patch_deepseek_reasoning_payload(input_: Any, payload: dict[str, Any]) -> None:
    """Propagate reasoning_content back into DeepSeek chat/completions payload."""
    if isinstance(input_, list):
        source_messages = input_
    elif hasattr(input_, "to_messages"):
        source_messages = input_.to_messages()
    else:
        return

    payload_messages = payload.get("messages")
    if not isinstance(payload_messages, list):
        return

    for source, target in zip(source_messages, payload_messages, strict=False):
        if not isinstance(source, AIMessage) or not isinstance(target, dict):
            continue
        target = cast(dict[str, Any], target)
        reasoning_content = source.additional_kwargs.get("reasoning_content")
        if reasoning_content:
            target["reasoning_content"] = reasoning_content
