"""
Health check router.
"""

from fastapi import APIRouter

from app.api.schemas.health import HealthResponse
from app.settings import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns the current health status and version of the API.
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
    )
