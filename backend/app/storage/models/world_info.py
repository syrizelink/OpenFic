# -*- coding: utf-8 -*-
"""
Model data WorldInfo.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class WorldInfo(SQLModel, table=True):
    """
    Model buku dunia.

    Attributes:
        id: Identifier unik buku dunia (nanoid).
        project_id: ID proyek terkait, opsional, boleh kosong bila tidak terkait proyek.
        name: Nama buku dunia.
        description: Deskripsi buku dunia.
        created_at: Waktu pembuatan.
        updated_at: Waktu pembaruan.
    """

    __tablename__ = "world_info"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str | None = Field(
        default=None, index=True, unique=True, foreign_key="projects.id"
    )
    name: str = Field(max_length=200)
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

