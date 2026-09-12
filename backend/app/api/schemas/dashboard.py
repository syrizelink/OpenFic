# -*- coding: utf-8 -*-
"""
Dashboard API Schemas - Model respons dasbor statistik LLM API.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """Metrik ikhtisar dasbor."""

    calls_total: int = Field(description="Jumlah total pemanggilan LLM API")
    success_total: int = Field(description="Jumlah pemanggilan yang berhasil")
    tokens_total: int = Field(description="Total konsumsi token")
    tokens_input_total: int = Field(description="Jumlah total token masukan")
    tokens_output_total: int = Field(description="Jumlah total token keluaran")
    avg_latency_ms: float = Field(description="Latensi rata-rata (milidetik)")
    avg_first_token_ms: float = Field(description="Latensi token pertama rata-rata (milidetik)")


class DashboardModelTimeSeriesPoint(BaseModel):
    """Titik data tren yang diagregasi per tanggal dan model."""

    date: str = Field(description="Tanggal, format YYYY-MM-DD")
    key: str = Field(description="Kunci model")
    label: str = Field(description="Nama tampilan model")
    calls: int = Field(description="Jumlah pemanggilan")
    tokens_total: int = Field(description="Total konsumsi token")
    avg_latency_ms: float = Field(description="Latensi rata-rata (milidetik)")


class DashboardBreakdownItem(BaseModel):
    """Item statistik per grup."""

    key: str = Field(description="Kunci grup")
    label: str = Field(description="Nama tampilan")
    calls: int = Field(description="Jumlah pemanggilan")
    tokens_total: int = Field(description="Total konsumsi token")


class DashboardFilterOptionItem(BaseModel):
    """Item tampilan opsi filter."""

    value: str = Field(description="Nilai filter")
    label: str = Field(description="Nama tampilan")


class DashboardAuditRecord(BaseModel):
    """Item daftar catatan audit dasbor."""

    id: str = Field(description="ID catatan audit")
    created_at: datetime = Field(description="Waktu pembuatan")
    task_id: str | None = Field(default=None, description="Task ID")
    session_id: str | None = Field(default=None, description="ID sesi")
    project_id: str = Field(description="ID proyek")
    project_title: str | None = Field(default=None, description="Judul proyek")
    chapter_id: str | None = Field(default=None, description="ID bab")
    revision_id: str | None = Field(default=None, description="Revision ID")
    category: str = Field(description="Kategori pemanggilan")
    operation: str = Field(description="Operasi pemanggilan")
    model_id: str = Field(description="ID model")
    model_provider: str | None = Field(default=None, description="Penyedia model")
    model_name: str | None = Field(default=None, description="Nama model")
    tokens_input: int = Field(description="Jumlah token masukan")
    tokens_output: int = Field(description="Jumlah token keluaran")
    tokens_total: int = Field(description="Jumlah token total")
    token_cache: int = Field(description="Jumlah token cache hit")
    latency_ms: int | None = Field(default=None, description="Latensi pemanggilan API")
    first_token_ms: int | None = Field(default=None, description="Latensi token pertama")
    status: str = Field(description="Status pemanggilan")
    error_type: str | None = Field(default=None, description="Tipe error")
    error_message: str | None = Field(default=None, description="Pesan error")
    error_status_code: int | None = Field(default=None, description="Kode error HTTP")
    tool_calls_count: int = Field(description="Jumlah pemanggilan tool")
    has_request_messages: bool = Field(description="Apakah tersedia prompt masukan yang dapat dilihat")
    tool_references: str | None = Field(default=None, description="JSON definisi tool yang dibawa permintaan")
    response_content: str | None = Field(default=None, description="Teks keluaran model")
    response_tool_calls: str | None = Field(default=None, description="JSON pemanggilan tool oleh model")


class DashboardRecordPrompt(BaseModel):
    """Detail prompt masukan catatan pemanggilan."""

    id: str = Field(description="ID catatan audit")
    request_messages: str | None = Field(default=None, description="JSON pesan prompt masukan")


class DashboardRecordList(BaseModel):
    """Daftar catatan audit dengan paginasi."""

    items: list[DashboardAuditRecord] = Field(description="Daftar catatan")
    total: int = Field(description="Jumlah total catatan")
    page: int = Field(description="Nomor halaman saat ini")
    page_size: int = Field(description="Jumlah per halaman")


class WritingActivitySummary(BaseModel):
    """Ringkasan event aktivitas penulisan."""

    active_days: int = Field(description="Jumlah hari dengan aktivitas penulisan")
    creative_chapters: int = Field(description="Jumlah bab dengan aktivitas kreatif")


class WritingActivityTimeSeriesPoint(BaseModel):
    """Titik data aktivitas penulisan yang diagregasi per tanggal."""

    date: str = Field(description="Tanggal, format YYYY-MM-DD")
    user_word_delta: int = Field(description="Perubahan jumlah kata hasil suntingan pengguna")
    agent_word_delta: int = Field(description="Perubahan jumlah kata hasil modifikasi Agent")
    import_word_delta: int = Field(description="Perubahan jumlah kata dari inisialisasi impor")


class WritingDashboardResponse(BaseModel):
    """Respons dasbor statistik penulisan."""

    summary: WritingActivitySummary = Field(description="Ringkasan aktivitas penulisan")
    time_series: list[WritingActivityTimeSeriesPoint] = Field(description="Tren aktivitas penulisan")


class DashboardFilterOptions(BaseModel):
    """Opsi filter dasbor."""

    project_ids: list[str] = Field(description="Daftar ID proyek")
    model_providers: list[str] = Field(description="Daftar penyedia model")
    model_ids: list[str] = Field(description="Daftar ID model")
    categories: list[str] = Field(description="Daftar kategori pemanggilan")
    operations: list[str] = Field(description="Daftar operasi pemanggilan")
    statuses: list[str] = Field(description="Daftar status")
    project_options: list[DashboardFilterOptionItem] = Field(default_factory=list, description="Item tampilan filter proyek")
    model_options: list[DashboardFilterOptionItem] = Field(default_factory=list, description="Item tampilan filter model")


class DashboardStatsResponse(BaseModel):
    """Respons dasbor statistik LLM API."""

    summary: DashboardSummary = Field(description="Metrik ikhtisar")
    model_time_series: list[DashboardModelTimeSeriesPoint] = Field(description="Tren waktu yang diagregasi per model")
    by_model: list[DashboardBreakdownItem] = Field(description="Statistik per model")
    by_project: list[DashboardBreakdownItem] = Field(description="Statistik per proyek")
    options: DashboardFilterOptions = Field(description="Opsi filter")


class DashboardRecordsResponse(BaseModel):
    """Respons catatan pemanggilan LLM API."""

    options: DashboardFilterOptions = Field(description="Opsi filter")
    records: DashboardRecordList = Field(description="Daftar catatan")
