"""Normalize structured LangChain content blocks for text-only application surfaces."""

from typing import Any


def extract_text_content(content: Any) -> str:
    """Return text from plain content or standard LangChain content blocks."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def extract_reasoning_content(content: Any) -> str:
    """Return reasoning from Anthropic-style content blocks."""
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "reasoning":
            reasoning = block.get("reasoning")
            if isinstance(reasoning, str):
                parts.append(reasoning)
        elif block.get("type") == "thinking":
            thinking = block.get("thinking")
            if isinstance(thinking, str):
                parts.append(thinking)
    return "".join(parts)
