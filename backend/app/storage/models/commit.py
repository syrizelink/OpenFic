# -*- coding: utf-8 -*-
"""
Model data Commit - catatan perubahan tingkat bab.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Commit(SQLModel, table=True):
    """
    Catatan perubahan tingkat bab.

    Satu Commit mencatat perubahan konkret satu bab dalam sebuah Revision.

    Attributes:
        id: Identifier unik perubahan (nanoid).
        revision_id: ID versi pemilik.
        chapter_id: ID bab.
        operation: Jenis operasi (create/update/delete).
        snapshot_title: Judul sebelum perubahan.
        snapshot_content: Isi sebelum perubahan.
        snapshot_word_count: Jumlah kata sebelum perubahan.
        snapshot_order: Urutan sebelum perubahan.
        new_title: Judul setelah perubahan.
        new_content: Isi setelah perubahan.
        new_word_count: Jumlah kata setelah perubahan.
        new_order: Urutan setelah perubahan.
        created_at: Waktu pembuatan.
    """

    __tablename__ = "commits"

    id: str = Field(default_factory=generate_id, primary_key=True)
    revision_id: str = Field(index=True, foreign_key="revisions.id")
    chapter_id: str = Field(index=True, foreign_key="chapters.id")

    # Jenis perubahan: create, update, delete
    operation: str = Field(max_length=20, description="Jenis operasi: create/update/delete")

    # Data potret (menyimpan keadaan sebelum perubahan)
    snapshot_title: str | None = Field(default=None, max_length=200)
    snapshot_content: str | None = Field(default=None)
    snapshot_content_blob_id: str | None = Field(
        default=None,
        description="blob id content-addressed untuk teks sebelum perubahan (dipakai bila teks panjang)",
    )
    snapshot_word_count: int | None = Field(default=None)
    snapshot_order: int | None = Field(default=None)

    # Data setelah perubahan (untuk redo atau melihat perubahan)
    new_title: str | None = Field(default=None, max_length=200)
    new_content: str | None = Field(default=None)
    new_content_blob_id: str | None = Field(
        default=None,
        description="blob id content-addressed untuk teks setelah perubahan (dipakai bila teks panjang)",
    )
    new_word_count: int | None = Field(default=None)
    new_order: int | None = Field(default=None)

    # Cap waktu
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))