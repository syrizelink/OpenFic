# -*- coding: utf-8 -*-
"""
Model data untuk Model.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id
from app.models.clients.model_params import (
    DEFAULT_CONTEXT_LENGTH,
    MAX_CONTEXT_LENGTH,
)


class Model(SQLModel, table=True):
    """
    Model konfigurasi model.

    Attributes:
        id: identifier unik model (nanoid).
        name: nama model.
        remark: catatan.
        provider_id: ID penyedia yang terkait.
        model_id: ID model yang diperoleh dari penyedia.
        task_type: jenis tugas (llm, embedding, atau rerank).
        temperature: parameter Temperature (khusus LLM).
        top_p: parameter Top P (khusus LLM).
        top_k: parameter Top K (khusus LLM).
        min_p: parameter Min P (khusus LLM).
        top_a: parameter Top A (khusus LLM).
        frequency_penalty: parameter Frequency Penalty (khusus LLM).
        presence_penalty: parameter Presence Penalty (khusus LLM).
        repetition_penalty: parameter Repetition Penalty (khusus LLM).
        max_tokens: parameter Max Tokens (khusus LLM).
        context_length: panjang konteks (khusus LLM).
        input_price: harga input biasa (dolar AS/juta token).
        output_price: harga output (dolar AS/juta token).
        cache_read_price: harga baca cache (dolar AS/juta token).
        cache_write_price: harga tulis cache (dolar AS/juta token).
        dimensions: dimensi embedding (khusus embedding).
        created_at: waktu pembuatan.
        updated_at: waktu perubahan terakhir.
    """

    __tablename__ = "models"

    id: str = Field(default_factory=generate_id, primary_key=True)
    name: str = Field(max_length=200)
    remark: str = Field(default="", max_length=500)
    provider_id: str = Field(foreign_key="model_providers.id", index=True)
    model_id: str = Field(
        max_length=200, description="Model ID from the provider (e.g., gpt-4, claude-3-opus)"
    )
    task_type: str = Field(
        default="llm",
        max_length=20,
        index=True,
        description="Task type: llm, embedding, or rerank",
    )
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=0, le=128)
    min_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_a: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    repetition_penalty: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    context_length: int = Field(default=DEFAULT_CONTEXT_LENGTH, ge=0, le=MAX_CONTEXT_LENGTH)
    input_price: float = Field(default=0.0, ge=0.0)
    output_price: float = Field(default=0.0, ge=0.0)
    cache_read_price: float = Field(default=0.0, ge=0.0)
    cache_write_price: float = Field(default=0.0, ge=0.0)

    # Embedding parameters (nullable)
    dimensions: int | None = Field(default=None, ge=1, description="Embedding dimensions")

    is_builtin: bool = Field(
        default=False, description="Apakah model bawaan (tidak dapat dihapus/diedit)"
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
