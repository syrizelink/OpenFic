# -*- coding: utf-8 -*-
"""
Model data PromptEntry.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class PromptEntry(SQLModel, table=True):
    """
    Model entri prompt (isi yang diversikan).

    Attributes:
        id: Identifier unik (nanoid).
        uid: Identifier pelacakan antarversi (UUID) - mengenali perubahan
            entri yang sama di versi berbeda.
        version_id: ID versi pemilik.
        name: Nama entri.
        role: Jenis peran (system/user/assistant).
        content: Isi prompt (teks asli beserta makro).
        order_index: Indeks urutan.
        is_enabled: Apakah aktif.
        token_count: Hitungan Token.
        created_at: Waktu pembuatan.
        updated_at: Waktu perubahan terakhir.
    """

    __tablename__ = "prompt_entries"

    id: str = Field(default_factory=generate_id, primary_key=True)
    uid: str = Field(index=True, description="Identifier pelacakan antarversi")
    version_id: str = Field(foreign_key="prompt_chain_versions.id")
    name: str = Field(max_length=200)
    role: str = Field(max_length=20, description="system/user/assistant")
    content: str = Field(description="Isi prompt")
    order_index: int = Field(description="Indeks urutan")
    is_enabled: bool = Field(default=True, description="Apakah aktif")
    token_count: int = Field(default=0, description="Hitungan Token")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
