# -*- coding: utf-8 -*-
"""Model data Task."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Task(SQLModel, table=True):
    """
    Model tugas percakapan AI.

    Attributes:
        id: Identifier unik tugas (nanoid).
        project_id: ID proyek pemilik.
        title: Judul tugas (diambil dari masukan pengguna pertama, maksimum 50 karakter).
        mode: Mode tugas.
        token_input: Total token masukan.
        token_output: Total token keluaran.
        token_cache: Total token yang kena cache.
        context_input_tokens: Jumlah token masukan pada panggilan LLM terakhir.
        cost: Akumulasi biaya panggilan LLM (dolar).
        current_revision_id: ID revision untuk checkpoint pesan pengguna saat ini.
        current_message_id: ID pesan pengguna terbaru saat ini.
        agent_session_id: ID sesi Agent yang terkait.
        is_running: Apakah tugas saat ini masih berjalan di latar belakang.
        is_favorited: Apakah difavoritkan.
        created_at: Waktu pembuatan.
        updated_at: Waktu perubahan terakhir.
    """

    __tablename__ = "tasks"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    title: str = Field(max_length=200)
    mode: str = Field(max_length=20, index=True)
    token_input: int = Field(default=0, ge=0)
    token_output: int = Field(default=0, ge=0)
    token_cache: int = Field(default=0, ge=0)
    context_input_tokens: int = Field(default=0, ge=0)
    cost: float = Field(default=0.0, ge=0.0)
    current_revision_id: str | None = Field(default=None, index=True, foreign_key="revisions.id")
    current_message_id: str | None = Field(default=None, index=True)
    agent_session_id: str | None = Field(default=None, index=True, description="ID sesi Agent")
    is_running: bool = Field(default=False, description="Apakah tugas berjalan di latar belakang")
    is_favorited: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
