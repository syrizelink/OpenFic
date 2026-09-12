# -*- coding: utf-8 -*-
"""
Runtime Config Router - Konfigurasi runtime yang dibaca frontend dan proses utama desktop.

API key proyek PostHog (prefiks phc_) adalah kunci publik, hanya dapat menulis event, sehingga aman dikirim ke klien.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings import settings
from app.storage.database import get_session
from app.storage.repos import setting_repo
from app.telemetry import SETTING_KEY_TELEMETRY_ENABLED, parse_telemetry_enabled

router = APIRouter(prefix="/runtime-config", tags=["runtime-config"])


class RuntimeConfigResponse(BaseModel):
    """Respons konfigurasi runtime."""

    posthog_enabled: bool = Field(description="Apakah telemetri error PostHog diaktifkan")
    posthog_api_key: str = Field(description="API key proyek PostHog (publik)")
    posthog_host: str = Field(description="Alamat pelaporan PostHog")
    cloud_only: bool = Field(description="Whether local retrieval/model features are disabled")


@router.get("", response_model=RuntimeConfigResponse, summary="Mengambil konfigurasi runtime")
async def get_runtime_config(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RuntimeConfigResponse:
    """Mengembalikan konfigurasi telemetri error; frontend dan proses utama desktop memakainya untuk menginisialisasi klien pelaporan."""
    setting = await setting_repo.get_by_key(session, SETTING_KEY_TELEMETRY_ENABLED)
    db_enabled = parse_telemetry_enabled(setting.value if setting else None)
    return RuntimeConfigResponse(
        posthog_enabled=db_enabled and bool(settings.posthog_api_key),
        posthog_api_key=settings.posthog_api_key,
        posthog_host=settings.posthog_host,
        cloud_only=settings.cloud_only,
    )
