# -*- coding: utf-8 -*-
"""
Model data WorldInfoEntry.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class WorldInfoEntry(SQLModel, table=True):
    """
    Model entri buku dunia.

    Attributes:
        id: Identifier unik entri (nanoid).
        world_info_id: ID buku dunia pemilik.
        uid: Nomor urut yang terlihat pengguna (mulai dari 1).
        name: Nama entri.
        order: Nomor urut.
        content: Isi entri.
        token_count: Jumlah Token.
        is_enabled: Status aktif.
        created_at: Waktu pembuatan.
        updated_at: Waktu pembaruan.
    """

    __tablename__ = "world_info_entries"

    id: str = Field(default_factory=generate_id, primary_key=True)
    world_info_id: str = Field(index=True, foreign_key="world_info.id")
    uid: int = Field(index=True)
    name: str = Field(max_length=200)
    order: int = Field(index=True)
    content: str = Field(default="")
    token_count: int = Field(default=0)
    is_enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


