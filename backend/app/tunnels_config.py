"""Persistent tunnel configuration with encrypted credentials."""

from __future__ import annotations

import json

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.settings import settings
from app.storage.repos import setting_repo
from app.tunnels import TunnelConfigUpdate, TunnelMode, Provider

SETTING_KEY_TUNNEL_CONFIG = "tunnel_config"


class TunnelConfig:
    def __init__(
        self,
        provider: Provider = "cloudflare",
        mode: TunnelMode = "quick",
        hostname: str | None = None,
        token: str | None = None,
    ) -> None:
        self.provider = provider
        self.mode = mode
        self.hostname = hostname
        self.token = token


def _encryption_service() -> EncryptionService:
    return EncryptionService(settings.encryption_key)


def parse_tunnel_config(raw_value: str | None) -> TunnelConfig:
    if not raw_value:
        return TunnelConfig()
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return TunnelConfig()
    if not isinstance(payload, dict):
        return TunnelConfig()

    provider = payload.get("provider")
    if provider not in {"cloudflare", "ngrok"}:
        provider = "cloudflare"
    mode = payload.get("mode")
    if mode not in {"quick", "managed-remote"}:
        mode = "quick"
    if provider == "ngrok" and mode == "managed-remote":
        mode = "quick"
    hostname = payload.get("hostname")
    hostname = hostname.strip() if isinstance(hostname, str) and hostname.strip() else None

    token = None
    encrypted_token = payload.get("token_encrypted")
    if isinstance(encrypted_token, str) and encrypted_token:
        try:
            token = _encryption_service().decrypt(encrypted_token)
        except Exception:
            logger.warning("Failed to decrypt persisted tunnel token")

    return TunnelConfig(provider=provider, mode=mode, hostname=hostname, token=token)


def serialize_tunnel_config(config: TunnelConfig) -> str:
    encrypted_token = _encryption_service().encrypt(config.token) if config.token else None
    return json.dumps(
        {
            "provider": config.provider,
            "mode": config.mode,
            "hostname": config.hostname,
            "token_encrypted": encrypted_token,
        },
        ensure_ascii=False,
    )


def public_tunnel_config(config: TunnelConfig) -> dict[str, object]:
    return {
        "provider": config.provider,
        "mode": config.mode,
        "hostname": config.hostname,
        "token_configured": bool(config.token),
    }


async def load_tunnel_config(session: AsyncSession) -> TunnelConfig:
    setting = await setting_repo.get_by_key(session, SETTING_KEY_TUNNEL_CONFIG)
    return parse_tunnel_config(setting.value if setting else None)


async def save_tunnel_config(session: AsyncSession, config: TunnelConfig) -> None:
    await setting_repo.upsert(
        session,
        SETTING_KEY_TUNNEL_CONFIG,
        serialize_tunnel_config(config),
    )


async def update_tunnel_config(
    session: AsyncSession,
    payload: TunnelConfigUpdate,
) -> TunnelConfig:
    current = await load_tunnel_config(session)
    provider = payload.provider if payload.provider is not None else current.provider
    mode = payload.mode if payload.mode is not None else current.mode
    if provider == "ngrok" and mode == "managed-remote":
        mode = "quick"
    hostname = (
        payload.hostname.strip() if payload.hostname and payload.hostname.strip() else None
        if "hostname" in payload.model_fields_set
        else current.hostname
    )
    token = current.token
    if "token" in payload.model_fields_set:
        token = payload.token.get_secret_value().strip() if payload.token else None
        token = token or None
    config = TunnelConfig(
        provider=provider,
        mode=mode,
        hostname=hostname,
        token=token,
    )
    await save_tunnel_config(session, config)
    return config
