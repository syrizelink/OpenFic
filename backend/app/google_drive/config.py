# -*- coding: utf-8 -*-
"""
Google Drive 同步的设置键与存取函数。

敏感值（Google 客户端凭据、refresh token）使用现有 Fernet 加密后存入 settings 表；
普通配置与每个项目的同步状态直接以字符串存储。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.settings import settings
from app.storage.repos import setting_repo

DRIVE_OAUTH_SCOPE = "https://www.googleapis.com/auth/drive.file"
DRIVE_OAUTH_AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
DRIVE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
DRIVE_API_BASE = "https://www.googleapis.com"
GOOGLE_DOCS_MIME = "application/vnd.google-apps.document"
DRIVE_FOLDER_NAME = "OpenFic"
DRIVE_DOC_SUFFIX = "（自动同步）"

DEFAULT_SYNC_INTERVAL_MINUTES = 10
AUTO_SYNC_MIN_GAP_SECONDS = 10
PERIODIC_CHECK_SECONDS = 60

# 加密存储的敏感值
_SETTING_KEY_GOOGLE_CLIENT_ID = "drive_google_client_id"
_SETTING_KEY_GOOGLE_CLIENT_SECRET = "drive_google_client_secret"
_SETTING_KEY_REFRESH_TOKEN = "drive_refresh_token"
_SETTING_KEY_ACCESS_TOKEN = "drive_access_token"

# 明文存储的普通配置
SETTING_KEY_ACCESS_TOKEN_EXPIRES_AT = "drive_access_token_expires_at"
SETTING_KEY_CONNECTED_EMAIL = "drive_connected_email"
SETTING_KEY_DRIVE_FOLDER_ID = "drive_folder_id"
SETTING_KEY_OAUTH_STATE = "drive_oauth_state"
SETTING_KEY_SYNC_INTERVAL_MINUTES = "drive_sync_interval_minutes"
SETTING_KEY_LAST_SYNC_ATTEMPT = "drive_last_sync_attempt"

# 每个项目的同步状态（key 后缀为 project_id）
_SETTING_PREFIX_PROJECT_ENABLED = "drive_project_enabled:"
_SETTING_PREFIX_PROJECT_FILE_ID = "drive_project_file_id:"
_SETTING_PREFIX_PROJECT_LAST_SYNCED_AT = "drive_project_last_synced_at:"
_SETTING_PREFIX_PROJECT_HASH = "drive_project_hash:"
_SETTING_PREFIX_PROJECT_DIRTY = "drive_project_dirty:"
_SETTING_PREFIX_PROJECT_ERROR = "drive_project_error:"
_PROJECT_SETTING_PREFIXES = (
    _SETTING_PREFIX_PROJECT_ENABLED,
    _SETTING_PREFIX_PROJECT_FILE_ID,
    _SETTING_PREFIX_PROJECT_LAST_SYNCED_AT,
    _SETTING_PREFIX_PROJECT_HASH,
    _SETTING_PREFIX_PROJECT_DIRTY,
    _SETTING_PREFIX_PROJECT_ERROR,
)


def _encryption() -> EncryptionService:
    return EncryptionService(settings.encryption_key)


# ---------------------------------------------------------------------------
# 通用存取
# ---------------------------------------------------------------------------


async def get_value(session: AsyncSession, key: str) -> str | None:
    """读取设置值，空字符串视为 None。"""
    setting = await setting_repo.get_by_key(session, key)
    if setting is None or setting.value == "":
        return None
    return setting.value


async def set_value(session: AsyncSession, key: str, value: str) -> None:
    await setting_repo.upsert(session, key, value)


async def delete_value(session: AsyncSession, key: str) -> None:
    await setting_repo.delete_by_key(session, key)


async def get_encrypted(session: AsyncSession, key: str) -> str | None:
    raw = await get_value(session, key)
    if raw is None:
        return None
    try:
        return _encryption().decrypt(raw)
    except Exception:
        return None


async def set_encrypted(session: AsyncSession, key: str, plaintext: str) -> None:
    await set_value(session, key, _encryption().encrypt(plaintext))


async def get_bool(session: AsyncSession, key: str) -> bool:
    value = await get_value(session, key)
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


async def set_bool(session: AsyncSession, key: str, value: bool) -> None:
    await set_value(session, key, "true" if value else "false")


async def get_int(session: AsyncSession, key: str, default: int) -> int:
    value = await get_value(session, key)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Google 客户端凭据
# ---------------------------------------------------------------------------


async def get_google_client_id(session: AsyncSession) -> str | None:
    return await get_encrypted(session, _SETTING_KEY_GOOGLE_CLIENT_ID) or os.getenv(
        "OPENFIC_GOOGLE_CLIENT_ID"
    )


async def get_google_client_secret(session: AsyncSession) -> str | None:
    return await get_encrypted(session, _SETTING_KEY_GOOGLE_CLIENT_SECRET) or os.getenv(
        "OPENFIC_GOOGLE_CLIENT_SECRET"
    )


async def set_google_client_credentials(
    session: AsyncSession, client_id: str, client_secret: str
) -> None:
    await set_encrypted(session, _SETTING_KEY_GOOGLE_CLIENT_ID, client_id.strip())
    await set_encrypted(session, _SETTING_KEY_GOOGLE_CLIENT_SECRET, client_secret.strip())


# ---------------------------------------------------------------------------
# 连接状态
# ---------------------------------------------------------------------------


async def get_refresh_token(session: AsyncSession) -> str | None:
    return await get_encrypted(session, _SETTING_KEY_REFRESH_TOKEN)


async def set_refresh_token(session: AsyncSession, token: str) -> None:
    await set_encrypted(session, _SETTING_KEY_REFRESH_TOKEN, token)


async def get_access_token(session: AsyncSession) -> str | None:
    return await get_encrypted(session, _SETTING_KEY_ACCESS_TOKEN)


async def set_access_token(session: AsyncSession, token: str) -> None:
    await set_encrypted(session, _SETTING_KEY_ACCESS_TOKEN, token)


async def get_connected_email(session: AsyncSession) -> str | None:
    return await get_value(session, SETTING_KEY_CONNECTED_EMAIL)


async def is_connected(session: AsyncSession) -> bool:
    return await get_refresh_token(session) is not None


async def clear_connection(session: AsyncSession) -> None:
    """清除 OAuth token 与连接状态，保留凭据与同步配置。"""
    for key in (
        _SETTING_KEY_REFRESH_TOKEN,
        _SETTING_KEY_ACCESS_TOKEN,
        SETTING_KEY_ACCESS_TOKEN_EXPIRES_AT,
        SETTING_KEY_CONNECTED_EMAIL,
        SETTING_KEY_OAUTH_STATE,
        SETTING_KEY_DRIVE_FOLDER_ID,
    ):
        await delete_value(session, key)


# ---------------------------------------------------------------------------
# 每个项目的同步状态
# ---------------------------------------------------------------------------


def _project_key(prefix: str, project_id: str) -> str:
    return f"{prefix}{project_id}"


async def is_project_sync_enabled(session: AsyncSession, project_id: str) -> bool:
    return await get_bool(session, _project_key(_SETTING_PREFIX_PROJECT_ENABLED, project_id))


async def set_project_sync_enabled(
    session: AsyncSession, project_id: str, enabled: bool
) -> None:
    await set_bool(
        session, _project_key(_SETTING_PREFIX_PROJECT_ENABLED, project_id), enabled
    )


async def get_project_file_id(session: AsyncSession, project_id: str) -> str | None:
    return await get_value(session, _project_key(_SETTING_PREFIX_PROJECT_FILE_ID, project_id))


async def set_project_file_id(
    session: AsyncSession, project_id: str, file_id: str
) -> None:
    await set_value(
        session, _project_key(_SETTING_PREFIX_PROJECT_FILE_ID, project_id), file_id
    )


async def get_project_last_synced_at(session: AsyncSession, project_id: str) -> str | None:
    return await get_value(
        session, _project_key(_SETTING_PREFIX_PROJECT_LAST_SYNCED_AT, project_id)
    )


async def set_project_last_synced_at(
    session: AsyncSession, project_id: str, value: str
) -> None:
    await set_value(
        session, _project_key(_SETTING_PREFIX_PROJECT_LAST_SYNCED_AT, project_id), value
    )


async def get_project_hash(session: AsyncSession, project_id: str) -> str | None:
    return await get_value(session, _project_key(_SETTING_PREFIX_PROJECT_HASH, project_id))


async def set_project_hash(session: AsyncSession, project_id: str, value: str) -> None:
    await set_value(session, _project_key(_SETTING_PREFIX_PROJECT_HASH, project_id), value)


async def is_project_dirty(session: AsyncSession, project_id: str) -> bool:
    return await get_bool(
        session, _project_key(_SETTING_PREFIX_PROJECT_DIRTY, project_id)
    )


async def set_project_dirty(
    session: AsyncSession, project_id: str, dirty: bool
) -> None:
    await set_bool(
        session, _project_key(_SETTING_PREFIX_PROJECT_DIRTY, project_id), dirty
    )


async def get_project_error(session: AsyncSession, project_id: str) -> str | None:
    return await get_value(
        session, _project_key(_SETTING_PREFIX_PROJECT_ERROR, project_id)
    )


async def set_project_error(
    session: AsyncSession, project_id: str, message: str
) -> None:
    await set_value(
        session, _project_key(_SETTING_PREFIX_PROJECT_ERROR, project_id), message
    )


async def clear_project_error(session: AsyncSession, project_id: str) -> None:
    await delete_value(session, _project_key(_SETTING_PREFIX_PROJECT_ERROR, project_id))


async def list_sync_enabled_project_ids(session: AsyncSession) -> list[str]:
    """列出所有已开启自动同步的项目 ID。"""
    settings_list = await setting_repo.get_all(session)
    result: list[str] = []
    for setting in settings_list:
        if not setting.key.startswith(_SETTING_PREFIX_PROJECT_ENABLED):
            continue
        project_id = setting.key[len(_SETTING_PREFIX_PROJECT_ENABLED):]
        if project_id and setting.value.strip().lower() in {"1", "true", "yes", "on"}:
            result.append(project_id)
    return result


@dataclass(frozen=True)
class DriveConnectionState:
    """同步面板所需的全局连接状态。"""

    has_credentials: bool
    connected: bool
    email: str | None
    folder_id: str | None
    interval_minutes: int


async def get_connection_state(session: AsyncSession) -> DriveConnectionState:
    client_id = await get_google_client_id(session)
    client_secret = await get_google_client_secret(session)
    return DriveConnectionState(
        has_credentials=bool(client_id and client_secret),
        connected=await is_connected(session),
        email=await get_connected_email(session),
        folder_id=await get_value(session, SETTING_KEY_DRIVE_FOLDER_ID),
        interval_minutes=await get_int(
            session, SETTING_KEY_SYNC_INTERVAL_MINUTES, DEFAULT_SYNC_INTERVAL_MINUTES
        ),
    )
