# -*- coding: utf-8 -*-
"""
Model data Chapter.
"""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Chapter(SQLModel, table=True):
    """
    Model bab novel.

    Attributes:
        id: Identifier unik bab (nanoid).
        project_id: ID proyek pemilik.
        title: Judul bab.
        content: Isi teks bab.
        word_count: Jumlah kata bab, default 0.
        order: Nomor urut.
        created_at: Waktu pembuatan.
        updated_at: Waktu perubahan terakhir.
    """

    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("volume_id", "order", name="uq_chapters_volume_order"),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    volume_id: str = Field(index=True, foreign_key="volumes.id")
    title: str = Field(max_length=200)
    content: str = Field(default="")
    word_count: int = Field(default=0)
    order: int = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
