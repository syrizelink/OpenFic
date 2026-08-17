"""联网搜索工具配置：provider 选择、API Key（加密存储）与扩展参数。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.settings import settings
from app.storage.repos import setting_repo

SETTING_KEY_WEB_SEARCH_CONFIG = "web_search_config"
DEFAULT_WEB_SEARCH_MAX_RESULTS = 8


class WebSearchSettings(BaseModel):
    provider: str = ""
    api_key: str = ""
    extras: dict[str, str] = Field(default_factory=dict)


def _encryption_service() -> EncryptionService:
    return EncryptionService(settings.encryption_key)


def _decrypt_api_key(encrypted: str) -> str:
    if not encrypted:
        return ""
    try:
        return _encryption_service().decrypt(encrypted)
    except Exception:
        return ""


def parse_web_search_settings(raw_value: str | None) -> WebSearchSettings:
    if not raw_value:
        return WebSearchSettings()
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return WebSearchSettings()
    if not isinstance(payload, dict):
        return WebSearchSettings()

    provider = payload.get("provider")
    api_key = payload.get("api_key")
    extras: dict[str, str] = {}
    raw_extras = payload.get("extras")
    if isinstance(raw_extras, dict):
        for key, value in raw_extras.items():
            if isinstance(value, str) and value:
                extras[key] = value

    return WebSearchSettings(
        provider=provider if isinstance(provider, str) else "",
        api_key=_decrypt_api_key(api_key if isinstance(api_key, str) else ""),
        extras=extras,
    )


def serialize_web_search_settings(web_search_settings: WebSearchSettings) -> str:
    api_key = ""
    if web_search_settings.api_key:
        try:
            api_key = _encryption_service().encrypt(web_search_settings.api_key)
        except Exception:
            api_key = ""
    return json.dumps(
        {
            "provider": web_search_settings.provider,
            "api_key": api_key,
            "extras": web_search_settings.extras,
        },
        ensure_ascii=False,
    )


async def load_web_search_config(session: AsyncSession) -> WebSearchSettings:
    setting = await setting_repo.get_by_key(session, SETTING_KEY_WEB_SEARCH_CONFIG)
    return parse_web_search_settings(setting.value if setting else None)


async def save_web_search_config(
    session: AsyncSession,
    web_search_settings: WebSearchSettings,
) -> None:
    await setting_repo.upsert(
        session,
        SETTING_KEY_WEB_SEARCH_CONFIG,
        serialize_web_search_settings(web_search_settings),
    )
