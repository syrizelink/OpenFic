# -*- coding: utf-8 -*-
"""
Model data PromptChainVersion.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


def generate_short_hash() -> str:
    """Menghasilkan hash 8 karakter sebagai identitas versi."""
    return generate_id()[:8]


class PromptChainVersion(SQLModel, table=True):
    """
    Model versi rantai prompt.

    Attributes:
        id: Identifier unik (nanoid).
        prompt_id: Identitas unik prompt.
        version_hash: Hash pendek versi (8 karakter, untuk identitas pengguna).
        version_number: Nomor versi semantik (v1, v2, v3...).
        parent_version_id: ID versi induk (opsional, untuk melacak relasi versi).
        is_active: Apakah berada pada cabang aktif saat ini.
        note: Catatan versi (opsional).
        created_at: Waktu pembuatan.
    """

    __tablename__ = "prompt_chain_versions"

    id: str = Field(default_factory=generate_id, primary_key=True)
    prompt_id: str = Field(max_length=300, index=True, description="Identitas unik prompt")
    version_hash: str = Field(default_factory=generate_short_hash, max_length=8, unique=True)
    version_number: int = Field(description="Nomor versi semantik")
    parent_version_id: str | None = Field(default=None, foreign_key="prompt_chain_versions.id")
    is_active: bool = Field(default=True, description="Apakah berada pada cabang aktif saat ini")
    note: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
