# -*- coding: utf-8 -*-
"""
WorldInfo API Schemas - Model permintaan/respons buku dunia.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class WorldInfoResponse(BaseModel):
    """Respons buku dunia."""

    id: str = Field(description="ID buku dunia")
    project_id: str | None = Field(description="ID proyek terkait, dapat kosong")
    name: str = Field(description="Nama buku dunia")
    description: str = Field(description="Deskripsi buku dunia")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu pembaruan")

    model_config = {"from_attributes": True}


class WorldInfoListResponse(BaseModel):
    """Respons daftar buku dunia."""

    items: list[WorldInfoResponse] = Field(description="Daftar buku dunia")
    total: int = Field(description="Jumlah total")
    page: int = Field(description="Nomor halaman saat ini")
    page_size: int = Field(description="Jumlah per halaman")


# ============== Schemas entri buku dunia ==============


class WorldInfoEntryCreate(BaseModel):
    """Permintaan pembuatan entri buku dunia."""

    name: str = Field(min_length=1, max_length=200, description="Nama entri")
    content: str = Field(default="", description="Isi entri")
    token_count: int = Field(default=0, ge=0, description="Jumlah Token")
    is_enabled: bool = Field(default=True, description="Status sakelar")


class WorldInfoEntryUpdate(BaseModel):
    """Permintaan pembaruan entri buku dunia."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None
    token_count: int | None = Field(default=None, ge=0)
    is_enabled: bool | None = None


class WorldInfoEntryMoveRequest(BaseModel):
    """Permintaan pemindahan entri buku dunia."""

    new_order: int = Field(ge=1, description="Posisi urutan baru")


class WorldInfoEntryBatchToggleRequest(BaseModel):
    """Permintaan pengalihan sakelar entri secara massal."""

    entry_ids: list[str] = Field(min_length=1, description="Daftar ID entri yang akan dialihkan")
    is_enabled: bool = Field(description="Status sakelar tujuan")


class WorldInfoEntryBatchDeleteRequest(BaseModel):
    """Permintaan penghapusan entri secara massal."""

    entry_ids: list[str] = Field(min_length=1, description="Daftar ID entri yang akan dihapus")


class WorldInfoEntryBatchToggleResponse(BaseModel):
    """Respons pengalihan sakelar entri secara massal."""

    updated_count: int = Field(description="Jumlah entri yang sudah diperbarui")


class WorldInfoEntryBatchDeleteResponse(BaseModel):
    """Respons penghapusan entri secara massal."""

    deleted_count: int = Field(description="Jumlah entri yang sudah dihapus")


class WorldInfoEntryResponse(BaseModel):
    """Respons entri buku dunia."""

    id: str = Field(description="ID entri")
    world_info_id: str = Field(description="ID buku dunia pemilik")
    uid: int = Field(description="Nomor urut yang terlihat pengguna")
    name: str = Field(description="Nama entri")
    order: int = Field(description="Nomor urut")
    content: str = Field(description="Isi entri")
    token_count: int = Field(description="Jumlah Token")
    is_enabled: bool = Field(description="Status sakelar")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu pembaruan")

    model_config = {"from_attributes": True}


class WorldInfoEntryBriefResponse(BaseModel):
    """Respons ringan entri buku dunia (untuk daftar, tanpa content)."""

    id: str = Field(description="ID entri")
    world_info_id: str = Field(description="ID buku dunia pemilik")
    uid: int = Field(description="Nomor urut yang terlihat pengguna")
    name: str = Field(description="Nama entri")
    order: int = Field(description="Nomor urut")
    token_count: int = Field(description="Jumlah Token")
    is_enabled: bool = Field(description="Status sakelar")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu pembaruan")

    model_config = {"from_attributes": True}


class WorldInfoEntryBriefListResponse(BaseModel):
    """Respons daftar ringan entri buku dunia."""

    items: list[WorldInfoEntryBriefResponse] = Field(description="Daftar entri")
    total: int = Field(description="Jumlah total")


class WorldInfoImportPreviewEntry(BaseModel):
    """Entri pratinjau impor buku dunia."""

    uid: int = Field(description="UID entri asli")
    name: str = Field(description="Nama entri setelah diimpor")
    content_preview: str = Field(description="Pratinjau isi")
    is_enabled: bool = Field(description="Status aktif setelah diimpor")


class WorldInfoImportPreviewResponse(BaseModel):
    """Respons pratinjau impor buku dunia."""

    entry_count: int = Field(description="Jumlah total entri")
    enabled_count: int = Field(description="Jumlah entri yang aktif")
    entries: list[WorldInfoImportPreviewEntry] = Field(description="Daftar entri pratinjau")


class WorldInfoImportResponse(BaseModel):
    """Respons impor buku dunia."""

    world_info_id: str = Field(description="ID buku dunia tujuan")
    imported_count: int = Field(description="Jumlah entri yang berhasil diimpor")


class WorldInfoImportMode(BaseModel):
    """Mode impor buku dunia."""

    mode: str = Field(description="Mode impor: append atau overwrite")


# ============== Schemas pencarian ==============


class WorldInfoEntrySearchMatch(BaseModel):
    """Item cocok pada pencarian."""

    line_number: int = Field(description="Nomor baris yang cocok (mulai dari 1)")
    line_text: str = Field(description="Teks baris yang cocok")


class WorldInfoEntrySearchResult(BaseModel):
    """Hasil pencarian satu entri."""

    entry_id: str = Field(description="ID entri")
    entry_name: str = Field(description="Nama entri")
    uid: int = Field(description="UID entri")
    matches: list[WorldInfoEntrySearchMatch] = Field(description="Daftar item yang cocok")


class WorldInfoEntrySearchResponse(BaseModel):
    """Respons pencarian."""

    results: list[WorldInfoEntrySearchResult] = Field(description="Daftar hasil pencarian")
    total_entries: int = Field(description="Jumlah total entri yang cocok")
    total_matches: int = Field(description="Jumlah total item yang cocok")
