# -*- coding: utf-8 -*-
"""
Project API Schemas - Model permintaan/respons proyek.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Permintaan pembuatan proyek."""

    title: str = Field(min_length=1, max_length=200, description="Judul proyek")
    description: str | None = Field(default=None, description="Sinopsis proyek")


class ProjectUpdate(BaseModel):
    """Permintaan pembaruan proyek."""

    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="Judul proyek"
    )
    description: str | None = Field(default=None, description="Sinopsis proyek")


class ProjectResponse(BaseModel):
    """Respons proyek."""

    id: str = Field(description="ID proyek")
    title: str = Field(description="Judul proyek")
    description: str | None = Field(description="Sinopsis proyek")
    word_count: int = Field(description="Jumlah kata terhitung")
    chapter_count: int = Field(description="Jumlah total bab")
    cover_url: str | None = Field(description="URL sampul")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu modifikasi terakhir")

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Respons daftar proyek."""

    items: list[ProjectResponse] = Field(description="Daftar proyek")
    total: int = Field(description="Jumlah total")
    page: int = Field(description="Nomor halaman saat ini")
    page_size: int = Field(description="Jumlah per halaman")
