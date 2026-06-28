from collections.abc import Iterable
import json

from app.agent_runtime.context.types import ContextMessage
from app.core.utils.tiktoken import get_encoding


def count_text_tokens(text: str) -> int:
    return len(get_encoding("o200k_base").encode(text))


def _message_token_text(message: ContextMessage) -> str:
    parts = [message.content or ""]
    if message.role == "assistant" and message.tool_calls:
        parts.append(
            json.dumps(
                message.tool_calls,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
                default=str,
            )
        )
    return "\n".join(part for part in parts if part)


def count_context_tokens(messages: Iterable[ContextMessage]) -> int:
    return sum(count_text_tokens(_message_token_text(message)) for message in messages)
