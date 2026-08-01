# -*- coding: utf-8 -*-
"""
Drive Router - Google Drive 同步 API。
"""

from secrets import token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.drive import (
    DriveAuthUrlResponse,
    DriveConfigResponse,
    DriveConfigUpdate,
    DriveProjectStatus,
    DriveProjectUpdate,
    DriveSyncResult,
)
from app.background.jobs import service as background_service
from app.google_drive import config as drive_config
from app.google_drive import oauth
from app.google_drive.errors import DriveError, DriveNotConfiguredError
from app.google_drive.service import sync_project
from app.storage.database import get_session
from app.storage.repos import chapter_repo, project_repo

router = APIRouter(prefix="/drive", tags=["drive"])

_CALLBACK_SUCCESS_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>已连接</title></head>
<body style="font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f6f6f4">
<div style="text-align:center"><h1 style="font-size:20px">✓ 已连接到 Google Drive</h1>
<p style="color:#666">可以关闭此窗口，回到 OpenFic 设置页继续。</p></div>
</body></html>"""

_CALLBACK_ERROR_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>连接失败</title></head>
<body style="font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f6f6f4">
<div style="text-align:center"><h1 style="font-size:20px">连接失败</h1>
<p style="color:#666">{message}</p></div>
</body></html>"""


@router.get(
    "/config",
    response_model=DriveConfigResponse,
    summary="获取 Google Drive 同步配置",
)
async def get_drive_config(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DriveConfigResponse:
    state = await drive_config.get_connection_state(session)
    return DriveConfigResponse(
        has_credentials=state.has_credentials,
        connected=state.connected,
        email=state.email,
        folder_id=state.folder_id,
        interval_minutes=state.interval_minutes,
        redirect_uri=oauth.resolve_redirect_uri(),
    )


@router.put(
    "/config",
    response_model=DriveConfigResponse,
    summary="更新 Google Drive 同步配置",
)
async def update_drive_config(
    data: DriveConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DriveConfigResponse:
    if data.client_id is not None or data.client_secret is not None:
        client_id = (data.client_id or "").strip()
        client_secret = (data.client_secret or "").strip()
        if not client_id or not client_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client ID 与 Client Secret 必须同时提供",
            )
        await drive_config.set_google_client_credentials(session, client_id, client_secret)
        # 凭据变化后旧 token 失效，需要重新授权。
        await drive_config.clear_connection(session)
    if data.interval_minutes is not None:
        await drive_config.set_value(
            session,
            drive_config.SETTING_KEY_SYNC_INTERVAL_MINUTES,
            str(max(1, min(1440, data.interval_minutes))),
        )
    await background_service.commit_and_notify(session)
    return await get_drive_config(session)


@router.get(
    "/auth-url",
    response_model=DriveAuthUrlResponse,
    summary="获取 Google 授权链接",
)
async def get_drive_auth_url(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DriveAuthUrlResponse:
    try:
        client_id, _client_secret = await oauth.get_google_credentials(session)
    except DriveNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    state = token_urlsafe(32)
    redirect_uri = oauth.resolve_redirect_uri()
    await drive_config.set_value(session, drive_config.SETTING_KEY_OAUTH_STATE, state)
    await background_service.commit_and_notify(session)
    return DriveAuthUrlResponse(
        auth_url=oauth.build_authorization_url(client_id, state, redirect_uri),
        redirect_uri=redirect_uri,
    )


@router.get(
    "/oauth/callback",
    response_class=HTMLResponse,
    summary="Google OAuth 回调",
)
async def drive_oauth_callback(
    session: Annotated[AsyncSession, Depends(get_session)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    if error:
        return HTMLResponse(
            _CALLBACK_ERROR_PAGE.format(message="用户取消了授权或授权失败")
        )

    expected_state = await drive_config.get_value(
        session, drive_config.SETTING_KEY_OAUTH_STATE
    )
    if not state or not expected_state or state != expected_state:
        return HTMLResponse(_CALLBACK_ERROR_PAGE.format(message="回调校验失败，请重试"))

    if not code:
        return HTMLResponse(_CALLBACK_ERROR_PAGE.format(message="缺少授权 code"))

    try:
        email = await oauth.exchange_code(session, code)
        await drive_config.set_value(
            session, drive_config.SETTING_KEY_CONNECTED_EMAIL, email
        )
        await drive_config.delete_value(session, drive_config.SETTING_KEY_OAUTH_STATE)
        await background_service.commit_and_notify(session)
        logger.info(f"Google Drive 连接成功: email={email}")
        return HTMLResponse(_CALLBACK_SUCCESS_PAGE)
    except DriveError as exc:
        logger.warning(f"Google Drive 授权回调失败: {exc}")
        return HTMLResponse(_CALLBACK_ERROR_PAGE.format(message=str(exc)))


@router.delete(
    "/connection",
    response_model=DriveConfigResponse,
    summary="断开 Google 连接",
)
async def disconnect_drive(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DriveConfigResponse:
    await drive_config.clear_connection(session)
    await background_service.commit_and_notify(session)
    return await get_drive_config(session)


@router.get(
    "/projects/{project_id}",
    response_model=DriveProjectStatus,
    summary="获取项目同步状态",
)
async def get_project_drive_status(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DriveProjectStatus:
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    file_id = await drive_config.get_project_file_id(session, project_id)
    chapter_metadata = await chapter_repo.list_export_metadata_by_project(
        session, project_id
    )
    return DriveProjectStatus(
        project_id=project.id,
        project_title=project.title,
        connected=await drive_config.is_connected(session),
        enabled=await drive_config.is_project_sync_enabled(session, project_id),
        file_id=file_id,
        doc_url=f"https://docs.google.com/document/d/{file_id}/edit" if file_id else None,
        last_synced_at=await drive_config.get_project_last_synced_at(session, project_id),
        chapter_count=len(chapter_metadata),
        word_count=sum(word_count for _c, _v, _t, word_count in chapter_metadata),
        error_message=await drive_config.get_project_error(session, project_id),
    )


@router.put(
    "/projects/{project_id}",
    response_model=DriveProjectStatus,
    summary="开启或关闭项目自动同步",
)
async def update_project_drive_status(
    project_id: str,
    data: DriveProjectUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DriveProjectStatus:
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    await drive_config.set_project_sync_enabled(session, project_id, data.enabled)
    if data.enabled:
        # 开启后尽快触发首次同步。
        await drive_config.set_project_dirty(session, project_id, True)
    await background_service.commit_and_notify(session)
    return await get_project_drive_status(project_id, session)


@router.post(
    "/projects/{project_id}/sync",
    response_model=DriveSyncResult,
    summary="立即同步项目到 Google Drive",
)
async def sync_project_to_drive(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DriveSyncResult:
    result = await sync_project(session, project_id, manual=True)
    await background_service.commit_and_notify(session)
    if result.status == "error":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message
        )
    return DriveSyncResult(**result.__dict__)
