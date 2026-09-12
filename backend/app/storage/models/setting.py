# -*- coding: utf-8 -*-
"""
Model data Setting.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Setting(SQLModel, table=True):
    """
    Model setelan pengguna, menyimpan konfigurasi dalam bentuk pasangan kunci-nilai.

    Attributes:
        id: Identifier unik setelan (nanoid).
        key: Nama kunci setelan, indeks unik.
        value: Nilai setelan, string berformat JSON.
        created_at: Waktu pembuatan.
        updated_at: Waktu perubahan terakhir.
    """

    __tablename__ = "settings"

    id: str = Field(default_factory=generate_id, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=100)
    value: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
