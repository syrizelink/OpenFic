# -*- coding: utf-8 -*-
"""Typed catalog models."""

from pydantic import BaseModel, Field


class CatalogProviderModelSummary(BaseModel):
    model_id: str = Field(description="Catalog model id")
    display_name: str = Field(description="Catalog model display name")
    task_type: str = Field(description="llm, embedding, or rerank")
    metadata: dict | None = Field(
        default=None, description="Catalog display metadata"
    )


class CatalogProviderSummary(BaseModel):
    provider_type: str = Field(description="OpenFic provider type")
    display_name: str = Field(description="Provider display name")
    default_url: str | None = Field(
        default=None, description="Suggested default base URL for this provider"
    )
    api: str | None = Field(
        default=None, description="Raw Models.dev api field for exact matching"
    )
    icon_path: str | None = Field(
        default=None, description="Locally served builtin icon path"
    )
    models_dev_provider_id: str | None = Field(
        default=None, description="Mapped Models.dev provider id"
    )
    supported_task_types: list[str] = Field(
        default_factory=list, description="Supported task types"
    )
    model_counts: dict[str, int] = Field(
        default_factory=dict, description="Counts grouped by task type"
    )


class CatalogProviderModelsResponse(BaseModel):
    provider: CatalogProviderSummary
    task_type: str
    models: list[CatalogProviderModelSummary]


class CatalogMatch(BaseModel):
    catalog_provider_type: str = Field(description="Matched catalog provider type")
    display_name: str = Field(description="Catalog display name")
    default_url: str | None = Field(default=None, description="Catalog default URL")
    api: str | None = Field(default=None, description="Catalog api field")
    icon_path: str | None = Field(default=None, description="Builtin icon path")
    models_dev_provider_id: str | None = Field(
        default=None, description="Mapped Models.dev provider id"
    )
    matched_via: str = Field(description="provider_type or api")
