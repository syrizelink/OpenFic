# -*- coding: utf-8 -*-
"""
Note API Schemas - Model permintaan/respons catatan.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NoteCategoryCreate(BaseModel):
    parent_id: str | None = Field(default=None, description="ID kategori induk")
    title: str = Field(min_length=1, max_length=200, description="Judul kategori")


class NoteCategoryUpdate(BaseModel):
    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="Judul kategori"
    )


class NoteCreate(BaseModel):
    category_id: str | None = Field(default=None, description="ID kategori pemilik")
    title: str = Field(min_length=1, max_length=200, description="Judul catatan")
    content: str = Field(default="", description="Isi catatan")


class NoteUpdate(BaseModel):
    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="Judul catatan"
    )
    content: str | None = Field(default=None, description="Isi catatan")


class NoteLockToggle(BaseModel):
    is_locked: bool = Field(description="Apakah terkunci")


class NoteHiddenToggle(BaseModel):
    is_hidden: bool = Field(description="Apakah tersembunyi")


class NoteItemMove(BaseModel):
    kind: Literal["category", "note"] = Field(description="Tipe pemindahan")
    item_id: str = Field(description="ID kategori/catatan yang dipindahkan")
    target_category_id: str | None = Field(default=None, description="ID kategori tujuan")


class NoteResponse(BaseModel):
    id: str = Field(description="ID catatan")
    project_id: str = Field(description="ID proyek pemilik")
    category_id: str | None = Field(description="ID kategori pemilik")
    title: str = Field(description="Judul catatan")
    content: str = Field(description="Isi catatan")
    is_locked: bool = Field(description="Apakah terkunci")
    is_hidden: bool = Field(description="Apakah tersembunyi")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu modifikasi terakhir")

    model_config = {"from_attributes": True}


class NoteListItem(BaseModel):
    id: str = Field(description="ID catatan")
    project_id: str = Field(description="ID proyek pemilik")
    category_id: str | None = Field(description="ID kategori pemilik")
    title: str = Field(description="Judul catatan")
    is_locked: bool = Field(description="Apakah terkunci")
    is_hidden: bool = Field(description="Apakah tersembunyi")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu modifikasi terakhir")

    model_config = {"from_attributes": True}


class NoteCategoryResponse(BaseModel):
    id: str = Field(description="ID kategori")
    project_id: str = Field(description="ID proyek pemilik")
    parent_id: str | None = Field(description="ID kategori induk")
    title: str = Field(description="Judul kategori")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu modifikasi terakhir")

    model_config = {"from_attributes": True}


class NoteCategoryItem(BaseModel):
    id: str = Field(description="ID kategori")
    project_id: str = Field(description="ID proyek pemilik")
    parent_id: str | None = Field(description="ID kategori induk")
    title: str = Field(description="Judul kategori")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu modifikasi terakhir")
    categories: list["NoteCategoryItem"] = Field(description="Daftar subkategori")
    notes: list[NoteListItem] = Field(description="Daftar catatan di dalam kategori")

    model_config = {"from_attributes": True}


class NoteTreeResponse(BaseModel):
    categories: list[NoteCategoryItem] = Field(description="Pohon kategori")
    root_notes: list[NoteListItem] = Field(description="Catatan level akar")
    total_notes: int = Field(description="Jumlah total catatan")


class NoteMoveResult(BaseModel):
    kind: Literal["category", "note"] = Field(description="Tipe pemindahan")
    note: NoteResponse | None = Field(default=None, description="Catatan yang dipindahkan")
    category: NoteCategoryResponse | None = Field(
        default=None, description="Kategori yang dipindahkan"
    )


NoteCategoryItem.model_rebuild()


class NoteSearchMatch(BaseModel):
    """Baris cocok pada pencarian isi catatan."""

    line_number: int = Field(description="Nomor baris yang cocok")
    line_text: str = Field(description="Teks baris yang cocok")


class NoteSearchResult(BaseModel):
    """Hasil pencarian isi catatan."""

    note_id: str = Field(description="ID catatan")
    note_title: str = Field(description="Judul catatan")
    category_path: str = Field(description="Path kategori pemilik")
    matches: list[NoteSearchMatch] = Field(description="Daftar baris yang cocok")


class NoteSearchResponse(BaseModel):
    """Respons pencarian isi catatan."""

    results: list[NoteSearchResult] = Field(description="Daftar hasil pencarian")
    total_notes: int = Field(description="Jumlah catatan yang cocok")
    total_matches: int = Field(description="Jumlah total baris yang cocok")


class NoteImportPreviewResponse(BaseModel):
    """Respons pratinjau impor catatan."""

    file_type: Literal["md", "zip"] = Field(description="Tipe berkas impor")
    note_count: int = Field(description="Jumlah catatan Markdown")
    category_count: int = Field(description="Jumlah kategori")
    ignored_file_count: int = Field(description="Jumlah berkas non-Markdown yang diabaikan")


class NoteImportResponse(BaseModel):
    """Respons impor catatan."""

    file_type: Literal["md", "zip"] = Field(description="Tipe berkas impor")
    imported_note_count: int = Field(description="Jumlah catatan yang diimpor")
    imported_category_count: int = Field(description="Jumlah kategori yang dibuat")
    ignored_file_count: int = Field(description="Jumlah berkas non-Markdown yang diabaikan")
