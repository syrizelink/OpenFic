# -*- coding: utf-8 -*-
"""
Chapter API Schemas - Model permintaan/respons bab.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChapterCreate(BaseModel):
    """Permintaan pembuatan bab."""

    volume_id: str = Field(description="ID volume pemilik")
    title: str = Field(min_length=1, max_length=200, description="Judul bab")
    content: str = Field(default="", description="Isi bab")
    word_count: int | None = Field(
        default=None, ge=0, description="Jumlah kata bab (dihitung frontend)"
    )


class ChapterUpdate(BaseModel):
    """Permintaan pembaruan bab."""

    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="Judul bab"
    )
    content: str | None = Field(default=None, description="Isi bab")
    word_count: int | None = Field(
        default=None, ge=0, description="Jumlah kata bab (dihitung frontend)"
    )


class ChapterReorder(BaseModel):
    """Permintaan penataan ulang bab secara massal."""

    volume_id: str = Field(description="ID volume")
    chapter_ids: list[str] = Field(description="Daftar ID bab dalam urutan baru")


class ChapterMoveToVolume(BaseModel):
    """Permintaan pemindahan bab antar volume."""

    volume_id: str = Field(description="ID volume tujuan")


class ChapterResponse(BaseModel):
    """Respons bab (versi lengkap, termasuk isi)."""

    id: str = Field(description="ID bab")
    project_id: str = Field(description="ID proyek pemilik")
    volume_id: str = Field(description="ID volume pemilik")
    title: str = Field(description="Judul bab")
    content: str = Field(description="Isi bab")
    word_count: int = Field(description="Jumlah kata bab")
    order: int = Field(description="Nomor urut")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu modifikasi terakhir")

    model_config = {"from_attributes": True}


class ChapterListItem(BaseModel):
    """Item daftar bab (versi ringkas, tanpa isi, untuk tampilan daftar)."""

    id: str = Field(description="ID bab")
    project_id: str = Field(description="ID proyek pemilik")
    volume_id: str = Field(description="ID volume pemilik")
    title: str = Field(description="Judul bab")
    word_count: int = Field(description="Jumlah kata bab")
    order: int = Field(description="Nomor urut")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu modifikasi terakhir")

    model_config = {"from_attributes": True}


class VolumeTreeItem(BaseModel):
    """Node volume pada pohon volume-bab."""

    id: str = Field(description="ID volume")
    project_id: str = Field(description="ID proyek pemilik")
    title: str = Field(description="Nama volume")
    description: str | None = Field(description="Deskripsi volume")
    order: int = Field(description="Nomor urut di dalam proyek")
    chapter_count: int = Field(description="Jumlah bab")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu modifikasi terakhir")
    chapters: list[ChapterListItem] = Field(description="Daftar bab di dalam volume")

    model_config = {"from_attributes": True}


class VolumeTreeResponse(BaseModel):
    """Respons pohon volume-bab."""

    volumes: list[VolumeTreeItem] = Field(description="Daftar volume")
    total_chapters: int = Field(description="Jumlah total bab")


class MentionCandidateItem(BaseModel):
    """Kandidat mention percakapan."""

    kind: Literal[
        "volume",
        "chapter",
        "note",
        "note_category",
        "world_info_entry",
        "character",
    ] = Field(description="Tipe kandidat")
    id: str = Field(description="ID volume atau bab")
    title: str = Field(description="Judul kandidat")
    label: str = Field(description="Label yang dipakai saat menyisipkan mention")
    description: str | None = Field(default=None, description="Keterangan tambahan")


class MentionCandidateSearchResponse(BaseModel):
    """Hasil pencarian kandidat mention."""

    items: list[MentionCandidateItem] = Field(description="Kandidat yang cocok")


class ChapterSearchMatch(BaseModel):
    """Baris cocok pada pencarian isi bab."""

    line_number: int = Field(description="Nomor baris yang cocok")
    line_text: str = Field(description="Teks baris yang cocok")


class ChapterSearchResult(BaseModel):
    """Hasil pencarian isi bab."""

    chapter_id: str = Field(description="ID bab")
    chapter_title: str = Field(description="Judul bab")
    volume_title: str = Field(description="Judul volume pemilik")
    matches: list[ChapterSearchMatch] = Field(description="Daftar baris yang cocok")


class ChapterSearchResponse(BaseModel):
    """Respons pencarian isi bab."""

    results: list[ChapterSearchResult] = Field(description="Daftar hasil pencarian")
    total_chapters: int = Field(description="Jumlah bab yang cocok")
    total_matches: int = Field(description="Jumlah total baris yang cocok")
