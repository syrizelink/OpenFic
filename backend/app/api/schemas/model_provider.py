# -*- coding: utf-8 -*-
"""
ModelProvider API Schemas - Model permintaan/respons penyedia layanan model.
"""

from typing import Any

from pydantic import BaseModel, Field


class CatalogMatchResponse(BaseModel):
    """Matched catalog provider metadata for a saved provider."""

    catalog_provider_type: str = Field(description="catalog provider_type yang cocok")
    display_name: str = Field(description="Nama tampilan penyedia Catalog")
    default_url: str | None = Field(default=None, description="URL default Catalog")
    api: str | None = Field(default=None, description="Field api Models.dev")
    icon_path: str | None = Field(default=None, description="Path ikon bawaan")
    models_dev_provider_id: str | None = Field(
        default=None, description="Models.dev provider id"
    )
    matched_via: str = Field(description="provider_type atau api")


class ModelProviderResponse(BaseModel):
    """Respons penyedia."""

    id: str = Field(description="ID penyedia")
    name: str = Field(description="Nama/catatan penyedia")
    url: str = Field(description="URL layanan")
    provider_type: str = Field(description="Tipe penyedia")
    custom_header_names: list[str] = Field(
        default_factory=list,
        description=(
            "Nama header permintaan kustom yang sudah dikonfigurasi (nilai header tidak "
            "dikembalikan)"
        ),
    )
    supported_task_types: list[str] = Field(
        description="Daftar tipe tugas yang didukung (llm, embedding, rerank)"
    )
    icon_path: str | None = Field(description="Path ikon Catalog")
    is_builtin: bool = Field(default=False, description="Apakah penyedia bawaan")
    catalog_match: CatalogMatchResponse | None = Field(
        default=None, description="Metadata penyedia catalog yang cocok"
    )
    created_at: str = Field(description="Waktu pembuatan")
    updated_at: str = Field(description="Waktu pembaruan")


class CustomHeaderEntry(BaseModel):
    """Satu header permintaan kustom."""

    key: str = Field(description="Nama header permintaan")
    value: str = Field(description="Nilai header permintaan")


class ModelProviderValidateRequest(BaseModel):
    """Permintaan validasi koneksi penyedia."""

    provider_type: str = Field(description="Tipe penyedia")
    url: str = Field(description="URL layanan")
    api_key: str = Field(description="API Key")
    custom_headers: list["CustomHeaderEntry"] = Field(
        default_factory=list,
        description="Header permintaan kustom",
    )


class AvailableModelMetadata(BaseModel):
    """Metadata tampilan model."""

    release_date: str | None = Field(default=None, description="Tanggal rilis model")
    reasoning: bool | None = Field(default=None, description="Apakah mendukung reasoning")
    tool_call: bool | None = Field(default=None, description="Apakah mendukung tool call")
    modalities: dict[str, list[str]] | None = Field(
        default=None, description="Modalitas masukan dan keluaran"
    )
    limit: dict[str, Any] | str | int | None = Field(
        default=None, description="Batas konteks dan keluaran"
    )
    cost: dict[str, Any] | str | int | None = Field(
        default=None, description="Metadata harga"
    )


class AvailableModel(BaseModel):
    """Model yang tersedia."""

    id: str = Field(description="ID model")
    name: str = Field(description="Nama model")
    task_type: str | None = Field(default=None, description="Tipe tugas")
    metadata: AvailableModelMetadata | None = Field(
        default=None, description="Metadata catalog yang cocok"
    )


class ModelProviderValidateResponse(BaseModel):
    """Respons validasi koneksi penyedia."""

    success: bool = Field(description="Apakah validasi berhasil")
    message: str = Field(description="Pesan")
    models: list[AvailableModel] = Field(description="Daftar model yang tersedia")
