from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

Role = Literal["system", "user", "assistant", "tool"]
Status = Literal["pending", "sent", "complete", "partial", "aborted"]

ROLE_VALUES: tuple[Role, ...] = ("system", "user", "assistant", "tool")
STATUS_VALUES: tuple[Status, ...] = ("pending", "sent", "complete", "partial", "aborted")


@dataclass
class PersistedMessage:
    id: str
    session_id: str
    task_id: str
    project_id: str
    role: Role
    agent_id: str | None
    content: str
    reasoning: str | None
    reasoning_duration_ms: int | None
    tool_calls: list[dict] | None
    tool_call_id: str | None
    tool_name: str | None
    status: Status
    message_type: str
    display_channel: str
    llm_visibility: str
    seq: int
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
