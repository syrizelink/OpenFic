# -*- coding: utf-8 -*-
"""Model provider catalog API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.catalog import (
    CatalogProviderModelsResponse,
    CatalogProviderSummary,
    CatalogStatus,
    ModelProviderCatalogService,
)

router = APIRouter(prefix="/model-provider-catalog", tags=["model-provider-catalog"])


def get_catalog_service() -> ModelProviderCatalogService:
    return ModelProviderCatalogService()


@router.get("/status", response_model=CatalogStatus, summary="Get catalog status")
async def get_catalog_status(
    service: Annotated[ModelProviderCatalogService, Depends(get_catalog_service)],
) -> CatalogStatus:
    return await service.get_status()


@router.get(
    "/providers",
    response_model=list[CatalogProviderSummary],
    summary="List catalog providers",
)
async def list_catalog_providers(
    service: Annotated[ModelProviderCatalogService, Depends(get_catalog_service)],
) -> list[CatalogProviderSummary]:
    return await service.list_providers()


@router.get(
    "/providers/{provider_type}/models",
    response_model=CatalogProviderModelsResponse,
    summary="List catalog models for a provider",
)
async def get_catalog_provider_models(
    provider_type: str,
    service: Annotated[ModelProviderCatalogService, Depends(get_catalog_service)],
    task_type: str = Query(..., pattern="^(llm|embedding|rerank)$"),
) -> CatalogProviderModelsResponse:
    try:
        return await service.get_provider_models(provider_type, task_type)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Catalog provider '{provider_type}' not found",
        )


@router.post("/refresh", response_model=CatalogStatus, summary="Refresh catalog cache")
async def refresh_catalog(
    service: Annotated[ModelProviderCatalogService, Depends(get_catalog_service)],
) -> CatalogStatus:
    return await service.refresh()
