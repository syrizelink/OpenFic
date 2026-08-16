# -*- coding: utf-8 -*-
"""
Runtime Config Router - 供前端与桌面主进程读取的运行时配置。

PostHog 项目 API key（phc_ 前缀）为公开密钥，仅可写入事件，可安全下发。
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
    """运行时配置响应。"""

    posthog_enabled: bool = Field(description="是否启用 PostHog 错误遥测")
    posthog_api_key: str = Field(description="PostHog 项目 API key（公开）")
    posthog_host: str = Field(description="PostHog 上报地址")


@router.get("", response_model=RuntimeConfigResponse, summary="获取运行时配置")
async def get_runtime_config(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RuntimeConfigResponse:
    """返回错误遥测配置，前端与桌面主进程据此初始化上报客户端。"""
    setting = await setting_repo.get_by_key(session, SETTING_KEY_TELEMETRY_ENABLED)
    db_enabled = parse_telemetry_enabled(setting.value if setting else None)
    return RuntimeConfigResponse(
        posthog_enabled=db_enabled and bool(settings.posthog_api_key),
        posthog_api_key=settings.posthog_api_key,
        posthog_host=settings.posthog_host,
    )
