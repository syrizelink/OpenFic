# -*- coding: utf-8 -*-
"""
Model data untuk ModelProvider.
"""

from datetime import UTC, datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class ModelProvider(SQLModel, table=True):
    """
    Model penyedia layanan model.

    Attributes:
        id: identifier unik penyedia (nanoid).
        name: nama/catatan penyedia (opsional, jika kosong ditampilkan sebagai URL).
        url: URL layanan.
        api_key_encrypted: API Key setelah dienkripsi.
        provider_type: jenis penyedia (Anthropic, OpenAI, Deepseek, dll).
        created_at: waktu pembuatan.
        updated_at: waktu perubahan terakhir.
    """

    __tablename__ = "model_providers"

    id: str = Field(default_factory=generate_id, primary_key=True)
    name: str = Field(default="", max_length=200)
    url: str = Field(max_length=500)
    api_key_encrypted: str = Field(max_length=1000)
    custom_headers_encrypted: str = Field(
        default="",
        sa_column=Column(Text, nullable=False),
    )
    provider_type: str = Field(
        max_length=50,
        description=(
            "Provider type: anthropic, openai, google-genai, ollama, groq, "
            "huggingface, mistral, nvidia-ai-endpoints, cohere, openrouter, "
            "amazon-nova, deepseek, openai-compatible, openai-compatible-responses, "
            "gemini-compatible"
        ),
    )
    is_builtin: bool = Field(
        default=False, description="Apakah penyedia bawaan (tidak dapat dihapus/diedit)"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
