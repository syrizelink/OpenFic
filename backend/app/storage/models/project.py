# -*- coding: utf-8 -*-
"""
Model data Project.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Project(SQLModel, table=True):
    """
    Model proyek novel.

    Attributes:
        id: Identifier unik proyek (nanoid).
        title: Judul proyek.
        description: Ringkasan proyek, boleh kosong.
        word_count: Jumlah kata terhitung, default 0.
        created_at: Waktu pembuatan.
        updated_at: Waktu perubahan terakhir.
    """

    __tablename__ = "projects"

    id: str = Field(default_factory=generate_id, primary_key=True)
    title: str = Field(max_length=200)
    description: str | None = Field(default=None)
    word_count: int = Field(default=0)
    chapter_count: int = Field(default=0)
    cover_path: str | None = Field(default=None, description="Path gambar sampul")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
