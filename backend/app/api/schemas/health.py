"""
Health check response schemas.
"""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


class MaintenanceResponse(BaseModel):
    """Local database maintenance status."""

    status: Literal["pending", "running", "ready", "failed"]
    phase: str
    progress: float | None
    deleted_rows: int
    reclaimed_pages: int
    total_pages: int
    elapsed_seconds: float
    message: str
    error: str | None
