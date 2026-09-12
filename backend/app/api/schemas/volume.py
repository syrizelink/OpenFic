# -*- coding: utf-8 -*-
"""
Volume API Schemas - Model permintaan/respons volume.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class VolumeCreate(BaseModel):
    """Permintaan pembuatan volume."""

    title: str = Field(min_length=1, max_length=200, description="Nama volume")
    description: str | None = Field(default=None, description="Deskripsi volume")


class VolumeUpdate(BaseModel):
    """Permintaan pembaruan volume."""

    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="Nama volume"
    )
    description: str | None = Field(default=None, description="Deskripsi volume")


class VolumeMove(BaseModel):
    """Permintaan pemindahan volume."""

    new_order: int = Field(ge=1, description="Posisi urutan baru")


class VolumeResponse(BaseModel):
    """Respons volume."""

    id: str = Field(description="ID volume")
    project_id: str = Field(description="ID proyek pemilik")
    title: str = Field(description="Nama volume")
    description: str | None = Field(description="Deskripsi volume")
    order: int = Field(description="Nomor urut di dalam proyek")
    chapter_count: int = Field(description="Jumlah bab")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu modifikasi terakhir")

    model_config = {"from_attributes": True}
