# -*- coding: utf-8 -*-
"""
Import API Schemas - Model permintaan/respons impor.
"""

from pydantic import BaseModel, Field


class PreviewChapter(BaseModel):
    """Informasi bab pratinjau."""

    title: str = Field(description="Judul bab")
    word_count: int = Field(description="Jumlah kata bab")
    content_preview: str = Field(description="Pratinjau isi (200 karakter pertama)")


class PreviewVolume(BaseModel):
    """Informasi volume pratinjau."""

    title: str = Field(description="Judul volume")
    chapter_count: int = Field(description="Jumlah bab di dalam volume")
    chapters: list[PreviewChapter] = Field(description="Daftar bab di dalam volume")


class ImportPreviewResponse(BaseModel):
    """Respons pratinjau impor."""

    volumes: list[PreviewVolume] = Field(description="Daftar volume")
    total_word_count: int = Field(description="Jumlah total kata")
    chapter_count: int = Field(description="Jumlah bab")
    detected_encoding: str = Field(description="Encoding yang terdeteksi")


class ImportConfirmRequest(BaseModel):
    """Permintaan konfirmasi impor."""

    title: str = Field(min_length=1, max_length=200, description="Judul buku")
    description: str | None = Field(default=None, description="Sinopsis")


class ImportConfirmResponse(BaseModel):
    """Respons konfirmasi impor."""

    project_id: str = Field(description="ID proyek yang dibuat")
    title: str = Field(description="Judul buku")
    chapter_count: int = Field(description="Jumlah bab yang diimpor")
    total_word_count: int = Field(description="Jumlah total kata")
