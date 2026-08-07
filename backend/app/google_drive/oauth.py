# -*- coding: utf-8 -*-
"""
Google OAuth2 桌面授权流程与 token 管理。

流程：
1. 后端生成授权 URL，前端用系统浏览器打开。
2. Google 回调到本机 `http://127.0.0.1:<port>/api/v1/drive/oauth/callback`。
3. 后端用 code 换取 token，refresh_token 加密存库。
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlencode

from app.google_drive import config as drive_config
from app.google_drive.errors import (
    DriveAuthError,
    DriveNotConfiguredError,
    DriveNotConnectedError,
)
from app.settings import settings


def resolve_redirect_uri() -> str:
    """解析 OAuth 回调地址（需与 Google Console 注册的完全一致）。"""
    port: str | None = os.getenv("OPENFIC_SERVER_PORT")
    if not port:
        port = _get_command_line_option("--port")
    if not port:
        port = str(settings.port)
    return f"http://127.0.0.1:{port}/api/v1/drive/oauth/callback"


def _get_command_line_option(option: str) -> str | None:
    option_with_value = f"{option}="
    for index, argument in enumerate(sys.argv):
        if argument.startswith(option_with_value):
            return argument.removeprefix(option_with_value)
        if argument == option and index + 1 < len(sys.argv):
            return sys.argv[index + 1]
    return None


def build_authorization_url(
    client_id: str, state: str, redirect_uri: str | None = None
) -> str:
    """构造 Google 授权 URL（access_type=offline 保证可刷新）。"""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri or resolve_redirect_uri(),
        "response_type": "code",
        "scope": drive_config.DRIVE_OAUTH_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{drive_config.DRIVE_OAUTH_AUTHORIZE_ENDPOINT}?{urlencode(params)}"


async def exchange_code(
    session: AsyncSession,
    code: str,
    redirect_uri: str | None = None,
) -> str:
    """用授权 code 换取 token 并存储；返回授权账号邮箱。"""
    client_id, client_secret = await get_google_credentials(session)
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri or resolve_redirect_uri(),
    }
    payload = await _request_tokens(data)
    await _store_tokens(session, payload)
    email = _email_from_payload(payload)
    await drive_config.set_value(
        session, drive_config.SETTING_KEY_CONNECTED_EMAIL, email or ""
    )
    return email or ""


async def get_access_token(session: AsyncSession) -> str:
    """返回可用的 access token；过期则用 refresh_token 刷新。"""
    token = await drive_config.get_access_token(session)
    expires_at = await drive_config.get_value(
        session, drive_config.SETTING_KEY_ACCESS_TOKEN_EXPIRES_AT
    )
    if token and _is_fresh(expires_at):
        return token

    refresh_token = await drive_config.get_refresh_token(session)
    if not refresh_token:
        raise DriveNotConnectedError("尚未连接 Google 账号")
    return await _refresh_access_token(session, refresh_token)


async def force_refresh_access_token(session: AsyncSession) -> str:
    """强制刷新 access token（收到 401 时重试）。"""
    refresh_token = await drive_config.get_refresh_token(session)
    if not refresh_token:
        raise DriveNotConnectedError("尚未连接 Google 账号")
    return await _refresh_access_token(session, refresh_token)


def _is_fresh(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        parsed = datetime.fromtimestamp(float(expires_at), tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return False
    return parsed > datetime.now(UTC)

async def _request_tokens(data: dict[str, str]) -> dict[str, object]:
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            drive_config.DRIVE_TOKEN_ENDPOINT, data=data
        )
    if response.status_code != 200:
        raise DriveAuthError(f"OAuth token 换取失败: {response.text[:200]}")
    payload = response.json()
    if not isinstance(payload, dict) or "access_token" not in payload:
        raise DriveAuthError("OAuth 响应缺少 access_token")
    return payload


async def _store_tokens(session: AsyncSession, payload: dict[str, object]) -> None:
    access_token = payload.get("access_token")
    if isinstance(access_token, str):
        await drive_config.set_access_token(session, access_token)
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, (int, float)):
            expires_at = datetime.now(UTC).timestamp() + float(expires_in) - 60
            await drive_config.set_value(
                session,
                drive_config.SETTING_KEY_ACCESS_TOKEN_EXPIRES_AT,
                str(int(expires_at)),
            )
    refresh_token = payload.get("refresh_token")
    if isinstance(refresh_token, str) and refresh_token:
        await drive_config.set_refresh_token(session, refresh_token)


def _email_from_payload(payload: dict[str, object]) -> str | None:
    """从 id_token 中解析账号邮箱（若返回）。"""
    id_token = payload.get("id_token")
    if not isinstance(id_token, str):
        return None
    try:
        # 仅做 Base64 解码取 email，不校验签名；邮箱仅用于展示。
        import base64
        import json

        encoded = id_token.split(".")[1]
        encoded += "=" * (-len(encoded) % 4)
        claims = json.loads(base64.urlsafe_b64decode(encoded))
        email = claims.get("email")
        return email if isinstance(email, str) and email else None
    except Exception:
        return None


async def _refresh_access_token(session: AsyncSession, refresh_token: str) -> str:
    client_id = await drive_config.get_google_client_id(session)
    client_secret = await drive_config.get_google_client_secret(session)
    if not client_id or not client_secret:
        raise DriveNotConfiguredError("未配置 Google 客户端凭据")
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        payload = await _request_tokens(data)
    except DriveAuthError as exc:
        await drive_config.clear_connection(session)
        raise DriveAuthError("Google 授权已失效，请重新连接") from exc
    await _store_tokens(session, payload)
    token = await drive_config.get_access_token(session)
    if not token:
        raise DriveAuthError("刷新 token 后仍无 access_token")
    return token


async def get_google_credentials(session: AsyncSession) -> tuple[str, str]:
    """返回 (client_id, client_secret)，未配置时抛错。"""
    client_id = await drive_config.get_google_client_id(session)
    client_secret = await drive_config.get_google_client_secret(session)
    if not client_id or not client_secret:
        raise DriveNotConfiguredError("请先在设置中配置 Google 客户端凭据")
    return client_id, client_secret
