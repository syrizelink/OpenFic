# -*- coding: utf-8 -*-
"""Model icon routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from app.models.catalog.icon_proxy import CatalogIconProxyError, CatalogIconProxyService

router = APIRouter(prefix="/icons/model", tags=["model-icons"])


def get_catalog_icon_proxy_service(request: Request) -> CatalogIconProxyService:
    return request.app.state.catalog_icon_proxy_service


@router.get("/catalog/{provider_file}", summary="Get a catalog provider icon")
async def get_catalog_provider_icon(
    provider_file: str,
    service: Annotated[
        CatalogIconProxyService, Depends(get_catalog_icon_proxy_service)
    ],
) -> Response:
    if not provider_file.endswith(".svg"):
        raise HTTPException(status_code=404, detail="Catalog provider icon not found")

    provider_id = provider_file[:-4]
    if not provider_id:
        raise HTTPException(status_code=404, detail="Catalog provider icon not found")

    try:
        payload = await service.fetch_icon(provider_id)
    except CatalogIconProxyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return Response(
        content=payload.content,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
