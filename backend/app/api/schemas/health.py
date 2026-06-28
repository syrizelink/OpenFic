"""
Health check response schemas.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
