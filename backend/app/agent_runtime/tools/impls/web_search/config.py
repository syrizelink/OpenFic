"""联网搜索工具配置：provider 选择、按 provider 加密存储的 API Key 与扩展参数。"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.agent_runtime.tools.impls.web_search.result_filter import normalize_domain_filters
from app.settings import settings
from app.storage.repos import setting_repo

SETTING_KEY_WEB_SEARCH_CONFIG = "web_search_config"
DEFAULT_WEB_SEARCH_MAX_RESULTS = 10
MAX_WEB_SEARCH_MAX_RESULTS = 20


class WebSearchSettings(BaseModel):
    enabled: bool = False
    provider: str = ""
    api_keys: dict[str, str] = Field(default_factory=dict)
    max_results: int = Field(default=DEFAULT_WEB_SEARCH_MAX_RESULTS, ge=1, le=20)
    domain_filters: list[str] = Field(default_factory=list)
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


def _decrypt_api_keys(raw_api_keys: object) -> dict[str, str]:
    if not isinstance(raw_api_keys, dict):
        return {}

    api_keys: dict[str, str] = {}
    for provider, encrypted in raw_api_keys.items():
        if not isinstance(provider, str) or not provider.strip():
            continue
        if not isinstance(encrypted, str):
            continue
        api_key = _decrypt_api_key(encrypted)
        if api_key:
            api_keys[provider.strip()] = api_key
    return api_keys
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
    enabled = payload.get("enabled")
    raw_max_results = payload.get("max_results")
    max_results = (
        raw_max_results
        if isinstance(raw_max_results, int)
        and not isinstance(raw_max_results, bool)
        and 1 <= raw_max_results <= MAX_WEB_SEARCH_MAX_RESULTS
        else DEFAULT_WEB_SEARCH_MAX_RESULTS
    )
    raw_domain_filters = payload.get("domain_filters")
    domain_filters = normalize_domain_filters(
        value for value in raw_domain_filters if isinstance(value, str)
    ) if isinstance(raw_domain_filters, list) else []
    raw_api_keys = payload.get("api_keys")
    if isinstance(raw_api_keys, dict):
        api_keys = _decrypt_api_keys(raw_api_keys)
    else:
        legacy_api_key = payload.get("api_key")
        api_keys = {}
        if isinstance(provider, str) and provider.strip() and isinstance(legacy_api_key, str):
            decrypted_api_key = _decrypt_api_key(legacy_api_key)
            if decrypted_api_key:
                api_keys[provider.strip()] = decrypted_api_key
    extras: dict[str, str] = {}
    raw_extras = payload.get("extras")
    if isinstance(raw_extras, dict):
        for key, value in raw_extras.items():
            if isinstance(value, str) and value:
                extras[key] = value

    return WebSearchSettings(
        enabled=enabled if isinstance(enabled, bool) else False,
        provider=provider if isinstance(provider, str) else "",
        api_keys=api_keys,
        max_results=max_results,
        domain_filters=domain_filters,
        extras=extras,
    )


def serialize_web_search_settings(web_search_settings: WebSearchSettings) -> str:
    api_keys: dict[str, str] = {}
    for provider, api_key in web_search_settings.api_keys.items():
        normalized_provider = provider.strip()
        normalized_api_key = api_key.strip()
        if not normalized_provider or not normalized_api_key:
            continue
        try:
            api_keys[normalized_provider] = _encryption_service().encrypt(normalized_api_key)
        except Exception:
            continue
    return json.dumps(
        {
            "enabled": web_search_settings.enabled,
            "provider": web_search_settings.provider,
            "api_keys": api_keys,
            "max_results": web_search_settings.max_results,
            "domain_filters": normalize_domain_filters(web_search_settings.domain_filters),
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
