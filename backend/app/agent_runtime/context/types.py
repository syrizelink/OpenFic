from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class ContextMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None
    additional_kwargs: dict | None = None
    metadata: dict | None = None
    attachments: list[dict[str, Any]] | None = None
