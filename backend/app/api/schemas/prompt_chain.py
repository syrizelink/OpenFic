# -*- coding: utf-8 -*-
"""
PromptChain API Schemas - Model permintaan/respons rantai prompt.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PromptEntryData(BaseModel):
    """Data entri prompt."""

    id: str | None = Field(default=None, description="ID entri (opsional)")
    uid: str | None = Field(default=None, description="Identifier pelacakan antar versi (opsional)")
    name: str = Field(min_length=1, max_length=200, description="Nama entri")
    role: str = Field(description="Tipe peran (system/user/assistant)")
    content: str = Field(description="Isi prompt")
    order_index: int = Field(ge=0, description="Indeks pengurutan")
    is_enabled: bool = Field(default=True, description="Apakah diaktifkan")
    token_count: int = Field(ge=0, description="Jumlah Token")


class PromptChainVersionResponse(BaseModel):
    """Respons versi rantai prompt."""

    id: str = Field(description="ID versi")
    prompt_id: str = Field(description="Identitas unik prompt")
    version_hash: str = Field(description="hash pendek versi")
    version_number: int = Field(description="Nomor versi semantik")
    parent_version_id: str | None = Field(description="ID versi induk")
    is_active: bool = Field(description="Apakah berada pada cabang aktif saat ini")
    note: str | None = Field(description="Catatan versi")
    created_at: datetime = Field(description="Waktu pembuatan")

    model_config = {"from_attributes": True}


class PromptEntryResponse(BaseModel):
    """Respons entri prompt."""

    id: str = Field(description="ID entri")
    uid: str = Field(description="Identifier pelacakan antar versi")
    version_id: str = Field(description="ID versi pemilik")
    name: str = Field(description="Nama entri")
    role: str = Field(description="Tipe peran")
    content: str = Field(description="Isi prompt")
    order_index: int = Field(description="Indeks pengurutan")
    is_enabled: bool = Field(description="Apakah diaktifkan")
    token_count: int = Field(description="Jumlah Token")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu pembaruan")

    model_config = {"from_attributes": True}


class PromptEntrySearchMatch(BaseModel):
    """Satu baris hasil pencarian pada entri prompt."""

    line_number: int = Field(description="Nomor baris, nama entri memakai 0")
    line_text: str = Field(description="Teks asli yang cocok")


class PromptEntrySearchResult(BaseModel):
    """Hasil pencarian satu entri prompt."""

    entry_id: str = Field(description="ID entri")
    entry_name: str = Field(description="Nama entri")
    role: str = Field(description="Tipe peran")
    matches: list[PromptEntrySearchMatch] = Field(description="Baris yang cocok")


class PromptEntrySearchResponse(BaseModel):
    """Respons pencarian entri di dalam versi prompt."""

    results: list[PromptEntrySearchResult] = Field(default_factory=list, description="Hasil pencarian")
    total_entries: int = Field(ge=0, description="Jumlah entri yang cocok")
    total_matches: int = Field(ge=0, description="Jumlah baris yang cocok")


class VersionWithEntriesResponse(BaseModel):
    """Respons versi beserta entrinya."""

    version: PromptChainVersionResponse = Field(description="Informasi versi")
    entries: list[PromptEntryResponse] = Field(description="Daftar entri")


class CreateVersionRequest(BaseModel):
    """Permintaan pembuatan versi baru."""

    parent_version_id: str = Field(description="ID versi induk")
    entries: list[PromptEntryData] = Field(description="Daftar entri")
    note: str | None = Field(default=None, max_length=500, description="Catatan versi")


class UpdateEntryRequest(BaseModel):
    """Permintaan pembaruan entri."""

    name: str | None = Field(default=None, min_length=1, max_length=200, description="Nama entri")
    role: str | None = Field(default=None, description="Tipe peran")
    content: str | None = Field(default=None, description="Isi prompt")
    order_index: int | None = Field(default=None, ge=0, description="Indeks pengurutan")
    is_enabled: bool | None = Field(default=None, description="Apakah diaktifkan")
    token_count: int | None = Field(default=None, ge=0, description="Jumlah Token")


class PromptMetadata(BaseModel):
    """Metadata satu prompt."""

    id: str = Field(description="Identitas unik prompt")
    label_key: str = Field(description="Kunci label internasionalisasi frontend")
    label: str | None = Field(default=None, description="Nama tampilan kustom")


class PromptCategoryMetadata(BaseModel):
    """Metadata kategori prompt."""

    id: str = Field(description="Identitas kategori")
    label_key: str = Field(description="Kunci label internasionalisasi frontend")
    prompts: list[PromptMetadata] = Field(default_factory=list, description="Daftar prompt")


class PromptChainsMetadataResponse(BaseModel):
    """Respons metadata rantai prompt."""

    categories: list[PromptCategoryMetadata] = Field(default_factory=list, description="Daftar kategori")


class CompiledEntryResponse(BaseModel):
    """Respons entri setelah dikompilasi."""

    name: str = Field(description="Nama entri")
    role: str = Field(description="Tipe peran")
    content: str = Field(description="Isi setelah dikompilasi")
    token_count: int = Field(ge=0, description="Jumlah Token")


class CompileResponse(BaseModel):
    """Respons kompilasi."""

    entries: list[CompiledEntryResponse] = Field(description="Daftar entri setelah dikompilasi")
    total_tokens: int = Field(ge=0, description="Jumlah Token total")


class EntryDiffResponse(BaseModel):
    """Respons perbedaan entri."""

    entry_id: str = Field(description="ID entri")
    change_type: str = Field(description="Tipe perubahan: added/deleted/modified")
    base_entry: PromptEntryResponse | None = Field(description="Entri pada versi basis")
    compare_entry: PromptEntryResponse | None = Field(description="Entri pada versi pembanding")


class VersionDiffResponse(BaseModel):
    """Respons perbedaan versi."""

    base_version: PromptChainVersionResponse = Field(description="Versi basis")
    compare_version: PromptChainVersionResponse = Field(description="Versi pembanding")
    diffs: list[EntryDiffResponse] = Field(description="Daftar perbedaan")
