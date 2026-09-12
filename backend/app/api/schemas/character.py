# -*- coding: utf-8 -*-
"""Character API Schemas - Model permintaan/respons tokoh."""

from datetime import datetime

from pydantic import BaseModel, Field


class CharacterResponse(BaseModel):
    """Respons tokoh."""

    id: str = Field(description="ID tokoh")
    project_id: str = Field(description="ID proyek pemilik")
    name: str = Field(description="Nama tokoh")
    description: str = Field(description="Deskripsi tokoh")
    image_url: str | None = Field(description="URL avatar tokoh")
    is_favorited: bool = Field(description="Apakah difavoritkan")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu pembaruan")


class CharacterListItemResponse(BaseModel):
    """Respons item daftar tokoh."""

    id: str = Field(description="ID tokoh")
    project_id: str = Field(description="ID proyek pemilik")
    name: str = Field(description="Nama tokoh")
    image_url: str | None = Field(description="URL avatar tokoh")
    token_count: int = Field(description="Jumlah Token deskripsi tokoh")
    is_favorited: bool = Field(description="Apakah difavoritkan")
    created_at: datetime = Field(description="Waktu pembuatan")
    updated_at: datetime = Field(description="Waktu pembaruan")


class CharacterListResponse(BaseModel):
    """Respons daftar tokoh."""

    items: list[CharacterListItemResponse] = Field(description="Daftar tokoh")
    total: int = Field(description="Jumlah total")


class CharacterSearchMatch(BaseModel):
    """Item cocok pada pencarian tokoh."""

    line_number: int = Field(description="Nomor baris yang cocok (mulai dari 1)")
    line_text: str = Field(description="Teks baris yang cocok")


class CharacterSearchResult(BaseModel):
    """Hasil pencarian satu tokoh."""

    character_id: str = Field(description="ID tokoh")
    character_name: str = Field(description="Nama tokoh")
    matches: list[CharacterSearchMatch] = Field(description="Daftar item yang cocok")


class CharacterSearchResponse(BaseModel):
    """Respons pencarian tokoh."""

    results: list[CharacterSearchResult] = Field(description="Daftar hasil pencarian")
    total_characters: int = Field(description="Jumlah total tokoh yang cocok")
    total_matches: int = Field(description="Jumlah total item yang cocok")


class CharacterBatchFavoriteRequest(BaseModel):
    """Permintaan favorit tokoh secara massal."""

    character_ids: list[str] = Field(min_length=1, description="Daftar ID tokoh yang akan diperbarui")
    is_favorited: bool = Field(description="Status favorit tujuan")


class CharacterBatchDeleteRequest(BaseModel):
    """Permintaan penghapusan tokoh secara massal."""

    character_ids: list[str] = Field(min_length=1, description="Daftar ID tokoh yang akan dihapus")


class CharacterBatchFavoriteResponse(BaseModel):
    """Respons favorit tokoh secara massal."""

    updated_count: int = Field(description="Jumlah tokoh yang sudah diperbarui")


class CharacterBatchDeleteResponse(BaseModel):
    """Respons penghapusan tokoh secara massal."""

    deleted_count: int = Field(description="Jumlah tokoh yang sudah dihapus")
