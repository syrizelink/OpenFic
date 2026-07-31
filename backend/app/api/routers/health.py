"""Health check and local server lifecycle routes."""

from hmac import compare_digest
from os import getenv

from fastapi import APIRouter, Header, HTTPException, Request, status

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


@router.post("/shutdown", status_code=status.HTTP_202_ACCEPTED)
async def request_shutdown(
    request: Request,
    shutdown_token: str | None = Header(default=None, alias="X-OpenFic-Shutdown-Token"),
) -> None:
    """Request a graceful shutdown from the desktop process that owns this server."""
    expected_token = getenv("OPENFIC_SHUTDOWN_TOKEN")
    if (
        not expected_token
        or shutdown_token is None
        or not compare_digest(shutdown_token, expected_token)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    server = getattr(request.app.state, "uvicorn_server", None)
    if server is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    server.should_exit = True
