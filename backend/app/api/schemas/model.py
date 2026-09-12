# -*- coding: utf-8 -*-
"""
Model API Schemas - Model permintaan/respons model.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.clients.model_params import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_FREQUENCY_PENALTY,
    DEFAULT_MIN_P,
    DEFAULT_PRESENCE_PENALTY,
    DEFAULT_REPETITION_PENALTY,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_A,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    MAX_CONTEXT_LENGTH,
)

TaskType = Literal["llm", "embedding", "rerank"]


class ModelResponse(BaseModel):
    """Respons model."""

    id: str = Field(description="ID model")
    name: str = Field(description="Nama model")
    remark: str = Field(description="Catatan")
    provider_id: str = Field(description="ID penyedia terkait")
    model_id: str = Field(description="ID model yang diambil dari penyedia")
    task_type: TaskType = Field(description="Tipe tugas (llm, embedding, atau rerank)")
    temperature: float | None = Field(description="Parameter Temperature (khusus LLM)")
    top_p: float | None = Field(description="Parameter Top P (khusus LLM)")
    top_k: int | None = Field(description="Parameter Top K (khusus LLM)")
    min_p: float | None = Field(description="Parameter Min P (khusus LLM)")
    top_a: float | None = Field(description="Parameter Top A (khusus LLM)")
    frequency_penalty: float | None = Field(
        description="Parameter Frequency Penalty (khusus LLM)"
    )
    presence_penalty: float | None = Field(
        description="Parameter Presence Penalty (khusus LLM)"
    )
    repetition_penalty: float | None = Field(
        description="Parameter Repetition Penalty (khusus LLM)"
    )
    max_tokens: int | None = Field(description="Parameter Max Tokens (khusus LLM)")
    context_length: int = Field(description="Panjang konteks (khusus LLM)")
    input_price: float = Field(description="Harga masukan biasa (dolar AS/juta token)")
    output_price: float = Field(description="Harga keluaran (dolar AS/juta token)")
    cache_read_price: float = Field(description="Harga baca cache (dolar AS/juta token)")
    cache_write_price: float = Field(description="Harga tulis cache (dolar AS/juta token)")
    dimensions: int | None = Field(description="Dimensi Embedding (khusus Embedding)")
    is_builtin: bool = Field(default=False, description="Apakah model bawaan")
    created_at: str = Field(description="Waktu pembuatan")
    updated_at: str = Field(description="Waktu pembaruan")


class ModelValidationResponse(BaseModel):
    """Respons validasi koneksi model."""

    success: bool = Field(description="Apakah validasi berhasil")
    message: str = Field(description="Pesan hasil validasi")


class ModelCreateRequest(BaseModel):
    """Permintaan pembuatan model."""

    name: str = Field(description="Nama model")
    provider_id: str = Field(description="ID penyedia terkait")
    model_id: str = Field(description="ID model yang diambil dari penyedia")
    task_type: TaskType = Field(
        default="llm", description="Tipe tugas (llm, embedding, atau rerank)"
    )
    remark: str = Field(default="", description="Catatan")
    temperature: float | None = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    top_p: float | None = Field(default=DEFAULT_TOP_P, ge=0.0, le=1.0)
    top_k: int | None = Field(default=DEFAULT_TOP_K, ge=0, le=128)
    min_p: float | None = Field(default=DEFAULT_MIN_P, ge=0.0, le=1.0)
    top_a: float | None = Field(default=DEFAULT_TOP_A, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(
        default=DEFAULT_FREQUENCY_PENALTY, ge=-2.0, le=2.0
    )
    presence_penalty: float | None = Field(
        default=DEFAULT_PRESENCE_PENALTY, ge=-2.0, le=2.0
    )
    repetition_penalty: float | None = Field(
        default=DEFAULT_REPETITION_PENALTY, ge=0.0, le=2.0
    )
    max_tokens: int | None = Field(
        default=None, description="Parameter Max Tokens (khusus LLM)"
    )
    context_length: int = Field(
        default=DEFAULT_CONTEXT_LENGTH, ge=0, le=MAX_CONTEXT_LENGTH
    )
    input_price: float = Field(default=0.0, ge=0.0)
    output_price: float = Field(default=0.0, ge=0.0)
    cache_read_price: float = Field(default=0.0, ge=0.0)
    cache_write_price: float = Field(default=0.0, ge=0.0)
    dimensions: int | None = Field(
        default=None, description="Dimensi Embedding (khusus Embedding)"
    )


class ModelUpdateRequest(BaseModel):
    """Permintaan pembaruan model."""

    name: str | None = Field(default=None, description="Nama model")
    remark: str | None = Field(default=None, description="Catatan")
    provider_id: str | None = Field(default=None, description="ID penyedia terkait")
    model_id: str | None = Field(default=None, description="ID model yang diambil dari penyedia")
    task_type: TaskType | None = Field(
        default=None, description="Tipe tugas (llm, embedding, atau rerank)"
    )
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=0, le=128)
    min_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_a: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    repetition_penalty: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(
        default=None, description="Parameter Max Tokens (khusus LLM)"
    )
    context_length: int | None = Field(default=None, ge=0, le=MAX_CONTEXT_LENGTH)
    input_price: float | None = Field(default=None, ge=0.0)
    output_price: float | None = Field(default=None, ge=0.0)
    cache_read_price: float | None = Field(default=None, ge=0.0)
    cache_write_price: float | None = Field(default=None, ge=0.0)
    dimensions: int | None = Field(
        default=None, description="Dimensi Embedding (khusus Embedding)"
    )
