# -*- coding: utf-8 -*-
"""
Audit API Schemas - Model permintaan/respons log audit.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ToolCallResult(BaseModel):
    """Hasil pemanggilan tool."""

    tool_name: str = Field(description="Nama tool")
    tool_args: dict = Field(description="Parameter tool")
    result: dict | None = Field(default=None, description="Hasil eksekusi")
    success: bool = Field(description="Apakah berhasil")
    latency_ms: int = Field(default=0, description="Durasi (milidetik)")


class LLMAuditLogResponse(BaseModel):
    """Respons log audit LLM."""

    id: str = Field(description="ID catatan audit")
    created_at: datetime = Field(description="Waktu pembuatan")

    task_id: str | None = Field(default=None, description="Task ID")
    session_id: str | None = Field(default=None, description="ID sesi Agent")
    parent_session_id: str | None = Field(
        default=None,
        description="ID sesi induk; kosong untuk pemanggilan sesi utama",
    )
    child_run_id: str | None = Field(
        default=None,
        description="ID run subagen; kosong untuk pemanggilan sesi utama",
    )
    project_id: str = Field(description="ID proyek")
    chapter_id: str | None = Field(default=None, description="ID bab")
    revision_id: str | None = Field(default=None, description="Revision ID")

    category: str = Field(description="Kategori pemanggilan")
    operation: str = Field(description="Operasi pemanggilan")
    call_sequence: int | None = Field(default=None, description="Nomor urut pemanggilan")

    model_id: str = Field(description="ID model")
    model_provider: str | None = Field(default=None, description="Penyedia model")
    model_name: str | None = Field(default=None, description="Nama model")

    request_messages: list[dict] | None = Field(
        default=None, description="Daftar pesan permintaan"
    )
    tool_references: list[dict] | None = Field(
        default=None, description="Daftar definisi tool yang dibawa permintaan"
    )
    response_content: str | None = Field(default=None, description="Isi respons")
    response_tool_calls: list[dict] | None = Field(
        default=None, description="Daftar pemanggilan tool pada respons"
    )
    tool_call_results: list[ToolCallResult] | None = Field(
        default=None, description="Daftar hasil pemanggilan tool"
    )

    tokens_input: int = Field(default=0, description="Jumlah token masukan")
    tokens_output: int = Field(default=0, description="Jumlah token keluaran")
    tokens_total: int = Field(default=0, description="Jumlah token total")
    token_cache: int = Field(default=0, description="Jumlah token cache hit")

    latency_ms: int | None = Field(default=None, description="Durasi pemanggilan API (milidetik)")
    first_token_ms: int | None = Field(default=None, description="Latensi Token pertama (milidetik)")

    status: str = Field(description="Status pemanggilan")
    error_type: str | None = Field(default=None, description="Tipe error")
    error_message: str | None = Field(default=None, description="Pesan error")
    error_status_code: int | None = Field(default=None, description="Kode error HTTP")

    tool_calls_count: int = Field(default=0, description="Jumlah total pemanggilan tool")
    tool_calls_success_count: int = Field(default=0, description="Jumlah pemanggilan tool yang berhasil")
    tool_calls_failed_count: int = Field(default=0, description="Jumlah pemanggilan tool yang gagal")


class LLMAuditLogListResponse(BaseModel):
    """Respons daftar log audit LLM."""

    items: list[LLMAuditLogResponse] = Field(description="Daftar log audit")
    total: int = Field(description="Jumlah total")


class TaskAuditAggregation(BaseModel):
    """Hasil agregat audit pada level Task."""

    task_id: str = Field(description="Task ID")
    llm_calls_total: int = Field(description="Jumlah total pemanggilan LLM")
    revisions_count: int = Field(description="Jumlah Revision")
    tokens_input_total: int = Field(description="Jumlah total token masukan")
    tokens_output_total: int = Field(description="Jumlah total token keluaran")
    tokens_grand_total: int = Field(description="Jumlah total token")
    duration_ms: int = Field(description="Total durasi (milidetik)")
    tool_calls_grand_total: int = Field(description="Jumlah total pemanggilan tool")
    has_error: bool = Field(description="Apakah terdapat error")
