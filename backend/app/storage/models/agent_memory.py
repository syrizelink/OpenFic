# -*- coding: utf-8 -*-
"""Model data AgentMemory - memori preferensi pengguna."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class AgentMemory(SQLModel, table=True):
    """Memori preferensi pengguna."""

    __tablename__ = "agent_memories"

    id: str = Field(default_factory=generate_id, primary_key=True)
    content: str = Field(default="")
    order_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
