# -*- coding: utf-8 -*-
"""
Task API Schemas - Model permintaan/respons tugas.
"""

from datetime import datetime
from pydantic import BaseModel, Field

from app.agent_runtime.modes import AgentMode


class TaskMessage(BaseModel):
    """Pesan tugas."""

    id: str = Field(description="ID pesan")
    task_id: str | None = Field(default=None, description="ID tugas")
    role: str = Field(description="Peran pesan: system, user, assistant, atau tool")
    agent_id: str | None = Field(default=None, description="ID Agent sumber pesan")
    content: str = Field(description="Isi pesan")
    tool_calls: list[dict] = Field(default_factory=list, description="Daftar pemanggilan tool yang dipicu pesan ini")
    tool_call_id: str | None = Field(default=None, description="ID pemanggilan tool terkait")
    metadata: dict = Field(default_factory=dict, description="Metadata tambahan")
    message_type: str | None = Field(default=None, description="Tipe pesan kanonik")
    message_status: str | None = Field(default=None, description="Status pesan kanonik")
    display_channel: str | None = Field(default=None, description="Kanal tampilan kanonik")
    payload: dict = Field(default_factory=dict, description="Payload pesan kanonik")
    correlation_id: str | None = Field(default=None, description="ID pesan/pemanggilan tool terkait")
    created_at: datetime = Field(description="Waktu pembuatan pesan")
    updated_at: datetime | None = Field(default=None, description="Waktu pembaruan pesan")


class TaskUpdateRequest(BaseModel):
    """Permintaan pembaruan tugas."""

    title: str | None = Field(default=None, description="Judul tugas")
    is_favorited: bool | None = Field(default=None, description="Apakah difavoritkan")

    model_config = {"extra": "forbid"}


class TaskResponse(BaseModel):
    """Respons tugas."""

    id: str = Field(description="ID tugas")
    project_id: str = Field(description="ID proyek")
    title: str = Field(description="Judul tugas")
    mode: AgentMode = Field(description="Tetap satu Agent runtime")
    messages: list[TaskMessage] = Field(description="Daftar pesan percakapan")
    token_input: int = Field(default=0, description="Jumlah total token masukan")
    token_output: int = Field(default=0, description="Jumlah total token keluaran")
    token_cache: int = Field(default=0, description="Jumlah total token cache hit")
    context_input_tokens: int = Field(default=0, description="Jumlah token masukan pada pemanggilan API sebelumnya")
    cost: float = Field(default=0.0, description="Biaya kumulatif (dolar AS)")
    current_revision_id: str | None = Field(default=None, description="ID revision yang sesuai dengan checkpoint pesan pengguna saat ini")
    current_message_id: str | None = Field(default=None, description="ID pesan pengguna terbaru saat ini")
    agent_session_id: str | None = Field(default=None, description="ID sesi Agent")
    is_running: bool = Field(default=False, description="Apakah tugas sedang berjalan di latar belakang")
    is_favorited: bool = Field(description="Apakah difavoritkan")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu pembaruan")


class TaskListItem(BaseModel):
    """Item daftar tugas."""

    id: str = Field(description="ID tugas")
    project_id: str = Field(description="ID proyek")
    title: str = Field(description="Judul tugas")
    mode: AgentMode = Field(description="Tetap satu Agent runtime")
    token_input: int = Field(default=0, description="Jumlah total token masukan")
    token_output: int = Field(default=0, description="Jumlah total token keluaran")
    token_cache: int = Field(default=0, description="Jumlah total token cache hit")
    context_input_tokens: int = Field(default=0, description="Jumlah token masukan pada pemanggilan API sebelumnya")
    cost: float = Field(default=0.0, description="Biaya kumulatif (dolar AS)")
    is_running: bool = Field(default=False, description="Apakah tugas sedang berjalan di latar belakang")
    is_favorited: bool = Field(description="Apakah difavoritkan")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu pembaruan")


class TaskListResponse(BaseModel):
    """Respons daftar tugas."""

    items: list[TaskListItem] = Field(description="Daftar tugas")
    total: int = Field(description="Jumlah total")
