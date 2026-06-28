"""Agent context compaction persistence DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


CompactionTrigger = Literal["auto", "manual"]


@dataclass(frozen=True)
class PersistedCompaction:
    id: str
    session_id: str
    task_id: str
    project_id: str
    start_seq: int
    end_seq: int
    summary: str
    trigger: CompactionTrigger
    source_input_tokens: int
    summary_tokens: int
    created_at: datetime


@dataclass(frozen=True)
class NewCompaction:
    session_id: str
    task_id: str
    project_id: str
    start_seq: int
    end_seq: int
    summary: str
    trigger: CompactionTrigger
    source_input_tokens: int = 0
    summary_tokens: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
