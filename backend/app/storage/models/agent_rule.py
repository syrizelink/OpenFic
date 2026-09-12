# -*- coding: utf-8 -*-
"""Model data AgentRule - aturan perilaku agen yang ditentukan pengguna."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class AgentRule(SQLModel, table=True):
    """Aturan perilaku agen yang ditentukan pengguna."""

    __tablename__ = "agent_rules"

    id: str = Field(default_factory=generate_id, primary_key=True)
    title: str = Field(default="")
    content: str = Field(default="")
    scope: str = Field(default="global", description="Cakupan: global atau project")
    project_id: str | None = Field(
        default=None, index=True, description="ID proyek yang terkait cakupan project"
    )
    token_count: int = Field(default=0, description="Jumlah token isi aturan")
    order_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
