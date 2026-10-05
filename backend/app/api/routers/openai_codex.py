"""OpenAI Codex OAuth routes for local self-hosted installations."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from dataclasses import replace
from html import escape
from os import getenv
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.agent_settings_lock import require_agent_settings_unlocked
from app.api.schemas.openai_codex import (
    OpenAICodexAuthStartRequest,
    OpenAICodexAuthStartResponse,
    OpenAICodexAuthStatusResponse,
    OpenAICodexManualCallbackRequest,
    OpenAICodexRegistrationResponse,
)
from app.core.encryption import EncryptionService
from app.models.services.openai_codex_service import (
    OPENAI_CODEX_API_BASE_URL,
    OPENAI_CODEX_CALLBACK_PATH,
    OPENAI_CODEX_DYNAMIC_CLIENT_ID,
    OPENAI_CODEX_ISSUER,
    OPENAI_CODEX_PROVIDER_TYPE,
    OpenAICodexError,
    OpenAICodexOAuthClient,
    OpenAICodexOAuthTransaction,
    OpenAICodexCredentialStore,
    openai_codex_provider_name,
    get_openai_codex_credentials,
    get_openai_codex_host_id,
    parse_openai_codex_callback,
    save_openai_codex_registration,
)
from app.models.repos import model_provider_oauth_registration_repo, model_provider_repo
from app.settings import BACKEND_DATA_DIR, settings
from app.storage.database import get_session


router = APIRouter(prefix="/openai-codex", tags=["openai-codex"])
_PENDING_TRANSACTIONS: dict[str, OpenAICodexOAuthTransaction] = {}
_IN_FLIGHT_TRANSACTIONS: dict[str, OpenAICodexOAuthTransaction] = {}
_DELETING_REGISTRATIONS: set[str] = set()
_TRANSACTION_RESULTS: dict[str, tuple[datetime, OpenAICodexAuthStatusResponse]] = {}
_PENDING_TRANSACTIONS_LOCK = asyncio.Lock()


def _encryption_service() -> EncryptionService:
    return EncryptionService(settings.encryption_key)


def _server_port() -> int:
    port = getenv("OPENFIC_SERVER_PORT")
    if port is not None:
        return int(port)
    for index, argument in enumerate(sys.argv):
        if argument.startswith("--port="):
            return int(argument.removeprefix("--port="))
        if argument == "--port" and index + 1 < len(sys.argv):
            return int(sys.argv[index + 1])
    return settings.port


async def _take_transaction(state: str) -> OpenAICodexOAuthTransaction | None:
    async with _PENDING_TRANSACTIONS_LOCK:
        transaction = _PENDING_TRANSACTIONS.pop(state, None)
        if transaction is None:
            return None
        if transaction.expires_at < datetime.now(UTC):
            return None
        _TRANSACTION_RESULTS[state] = (
            transaction.expires_at,
            OpenAICodexAuthStatusResponse(status="pending"),
        )
        _IN_FLIGHT_TRANSACTIONS[state] = transaction
        return transaction


def _callback_page(*, success: bool, message: str) -> HTMLResponse:
    safe_message = escape(message, quote=True)
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>OpenFic OpenAI Codex</title></head>
<body><p>{safe_message}</p>
</body></html>"""
    return HTMLResponse(
        content=html,
        status_code=200 if success else 400,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


async def _failed_callback(
    transaction: OpenAICodexOAuthTransaction, message: str
) -> tuple[bool, str]:
    async with _PENDING_TRANSACTIONS_LOCK:
        _IN_FLIGHT_TRANSACTIONS.pop(transaction.state, None)
        result = _TRANSACTION_RESULTS.get(transaction.state)
        if result and result[1].status == "cancelled":
            return False, "OpenAI Codex 授权已取消"
        _TRANSACTION_RESULTS[transaction.state] = (
            transaction.expires_at,
            OpenAICodexAuthStatusResponse(
                status="error",
                registration_id=transaction.expected_client_id if transaction.expected_client_id != OPENAI_CODEX_DYNAMIC_CLIENT_ID else None,
            ),
        )
    return False, message


@router.post(
    "/auth/start",
    response_model=OpenAICodexAuthStartResponse,
    summary="开始 OpenAI Codex 本地 OAuth 授权",
)
async def start_auth(
    request: OpenAICodexAuthStartRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OpenAICodexAuthStartResponse:
    async with _PENDING_TRANSACTIONS_LOCK:
        return await _start_auth(request, session)


async def _start_auth(
    request: OpenAICodexAuthStartRequest, session: AsyncSession,
) -> OpenAICodexAuthStartResponse:
    await require_agent_settings_unlocked(session)
    provider_id = request.provider_id
    if sum((bool(provider_id), bool(request.registration_id), request.new_registration)) > 1:
        raise HTTPException(status_code=400, detail="请选择已有注册或明确添加新账户，不能同时指定")
    expected_client_id = OPENAI_CODEX_DYNAMIC_CLIENT_ID
    expected_subject = None
    id_token_hint = None
    login_hint = None
    force_consent = False
    if provider_id:
        provider = await model_provider_repo.get_by_id(session, provider_id)
        if provider is None or provider.provider_type != OPENAI_CODEX_PROVIDER_TYPE:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OpenAI Codex 账户不存在")
        credentials = get_openai_codex_credentials(provider, _encryption_service())
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="OpenAI Codex 账户注册信息不可用，请重新添加账户",
            )
        expected_client_id = credentials.client_id
        if expected_client_id in _DELETING_REGISTRATIONS:
            raise HTTPException(status_code=409, detail="OAuth 注册正在删除")
        id_token_hint = credentials.id_token
        login_hint = credentials.email
        expected_subject = credentials.subject
        force_consent = not credentials.openai_codex_access_enabled
        await save_openai_codex_registration(session, credentials, provider_id)
        await session.commit()
    elif not request.new_registration:
        registrations = await OpenAICodexCredentialStore(_encryption_service()).list_registrations(
            session, deleting_client_ids=_DELETING_REGISTRATIONS,
        )
        selected = None
        if request.registration_id:
            selected = next((item for item in registrations if item.client_id == request.registration_id), None)
            if selected is None:
                raise HTTPException(status_code=404, detail="已保存的 OAuth 注册不存在")
        elif len(registrations) == 1:
            selected = registrations[0]
        elif len(registrations) > 1:
            raise HTTPException(status_code=409, detail="存在多个 OAuth 注册，请明确选择账户或工作区")
        if selected is not None:
            expected_client_id = selected.client_id
            expected_subject = selected.subject
            login_hint = selected.email
            provider_id = selected.provider_id
            if provider_id:
                provider = await model_provider_repo.get_by_id(session, provider_id)
                if provider is None:
                    provider_id = None
                else:
                    credentials = get_openai_codex_credentials(provider, _encryption_service())
                    id_token_hint = credentials.id_token if credentials else None
                    force_consent = bool(credentials and not credentials.openai_codex_access_enabled)

    if expected_client_id in _DELETING_REGISTRATIONS:
        raise HTTPException(status_code=409, detail="OAuth 注册正在删除")
    redirect_uri = f"http://127.0.0.1:{_server_port()}{OPENAI_CODEX_CALLBACK_PATH}"
    transaction = OpenAICodexOAuthClient().create_transaction(
        redirect_uri=redirect_uri,
        ext_agent_host_id=get_openai_codex_host_id(BACKEND_DATA_DIR),
        expected_client_id=expected_client_id,
        provider_id=provider_id,
        id_token_hint=id_token_hint,
        login_hint=login_hint,
        expected_subject=expected_subject,
        force_consent=force_consent,
    )
    now = datetime.now(UTC)
    for state in tuple(_PENDING_TRANSACTIONS):
        if _PENDING_TRANSACTIONS[state].expires_at < now:
            del _PENDING_TRANSACTIONS[state]
    for state in tuple(_TRANSACTION_RESULTS):
        if _TRANSACTION_RESULTS[state][0] < now and state not in _IN_FLIGHT_TRANSACTIONS:
            del _TRANSACTION_RESULTS[state]
    _PENDING_TRANSACTIONS[transaction.state] = transaction
    return OpenAICodexAuthStartResponse(
        authorization_url=OpenAICodexOAuthClient().authorization_url(transaction),
        authorization_id=transaction.state,
        provider_id=provider_id,
    )


@router.get("/registrations", response_model=list[OpenAICodexRegistrationResponse])
async def list_registrations(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[OpenAICodexRegistrationResponse]:
    async with _PENDING_TRANSACTIONS_LOCK:
        registrations = await OpenAICodexCredentialStore(_encryption_service()).list_registrations(
            session, deleting_client_ids=_DELETING_REGISTRATIONS,
        )
    return [OpenAICodexRegistrationResponse(
        client_id=item.client_id, email=item.email, provider_id=item.provider_id,
        verified=item.subject is not None,
    ) for item in registrations]


def _cancel_transaction(authorization_id: str) -> None:
    transaction = _PENDING_TRANSACTIONS.pop(authorization_id, None)
    transaction = transaction or _IN_FLIGHT_TRANSACTIONS.get(authorization_id)
    if transaction is not None:
        _TRANSACTION_RESULTS[authorization_id] = (
            transaction.expires_at, OpenAICodexAuthStatusResponse(status="cancelled"),
        )


@router.delete("/auth/{authorization_id}", response_model=OpenAICodexAuthStatusResponse)
async def cancel_auth(authorization_id: str) -> OpenAICodexAuthStatusResponse:
    async with _PENDING_TRANSACTIONS_LOCK:
        _cancel_transaction(authorization_id)
    return await auth_status(authorization_id)


@router.delete("/registrations/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def forget_registration(
    client_id: str, session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await require_agent_settings_unlocked(session)
    async with _PENDING_TRANSACTIONS_LOCK:
        if client_id in _DELETING_REGISTRATIONS:
            raise HTTPException(status_code=409, detail="OAuth 注册正在删除")
        _DELETING_REGISTRATIONS.add(client_id)
        for transaction in (*_PENDING_TRANSACTIONS.values(), *_IN_FLIGHT_TRANSACTIONS.values()):
            if transaction.expected_client_id == client_id:
                _cancel_transaction(transaction.state)
    try:
        confirmed = await OpenAICodexCredentialStore(_encryption_service()).forget_registration(session, client_id)
    finally:
        async with _PENDING_TRANSACTIONS_LOCK:
            _DELETING_REGISTRATIONS.discard(client_id)
    return Response(status_code=204, headers={"X-OAuth-Revocation-Confirmed": str(confirmed).lower()})


@router.get("/auth/status/{authorization_id}", response_model=OpenAICodexAuthStatusResponse)
async def auth_status(authorization_id: str) -> OpenAICodexAuthStatusResponse:
    async with _PENDING_TRANSACTIONS_LOCK:
        now = datetime.now(UTC)
        transaction = _PENDING_TRANSACTIONS.get(authorization_id)
        if transaction and transaction.expires_at > now:
            return OpenAICodexAuthStatusResponse(status="pending")
        result = _TRANSACTION_RESULTS.get(authorization_id)
        if result and result[0] > now:
            return result[1]
        _PENDING_TRANSACTIONS.pop(authorization_id, None)
        if authorization_id not in _IN_FLIGHT_TRANSACTIONS:
            _TRANSACTION_RESULTS.pop(authorization_id, None)
    return OpenAICodexAuthStatusResponse(status="expired")


async def _complete_authorization(
    parameters: Mapping[str, str], session: AsyncSession
) -> tuple[bool, str]:
    state = parameters.get("state")
    if not state:
        return False, "授权状态缺失，请重新开始授权"
    transaction = await _take_transaction(state)
    if transaction is None:
        return False, "授权状态已过期，请重新开始授权"

    oauth_error = parameters.get("error")
    if oauth_error:
        return await _failed_callback(transaction, "OpenAI Codex 授权被取消或拒绝")
    code = parameters.get("code")
    if not code:
        return await _failed_callback(transaction, "授权回调缺少 code")

    callback_client_id = parameters.get("client_id")
    oauth = OpenAICodexOAuthClient()
    try:
        await require_agent_settings_unlocked(session)
        client_id = oauth.validate_callback_client_id(
            returned_client_id=callback_client_id,
            expected_client_id=transaction.expected_client_id,
        )
        transaction = replace(transaction, expected_client_id=client_id)
        async with _PENDING_TRANSACTIONS_LOCK:
            _IN_FLIGHT_TRANSACTIONS[state] = transaction
            if client_id in _DELETING_REGISTRATIONS:
                _cancel_transaction(state)
            if _TRANSACTION_RESULTS[state][1].status == "cancelled":
                return False, "OpenAI Codex 授权已取消"
            await model_provider_oauth_registration_repo.save_issued(
                session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer=OPENAI_CODEX_ISSUER, client_id=client_id,
            )
            await session.commit()
        token_payload = await oauth.exchange_code(
            code=code,
            client_id=client_id,
            code_verifier=transaction.code_verifier,
            redirect_uri=transaction.redirect_uri,
        )
        credentials = await oauth.credentials_from_token_response(
            token_payload,
            client_id=client_id,
            nonce=transaction.nonce,
            ext_agent_host_id=transaction.ext_agent_host_id,
        )
        if transaction.expected_subject is not None and credentials.subject != transaction.expected_subject:
            raise OpenAICodexError("重新授权返回了不同的 OpenAI Codex 账户")
        async with _PENDING_TRANSACTIONS_LOCK:
            if client_id in _DELETING_REGISTRATIONS:
                _cancel_transaction(state)
            if _TRANSACTION_RESULTS[state][1].status == "cancelled":
                return False, "OpenAI Codex 授权已取消"
            try:
                await require_agent_settings_unlocked(session)
                existing = (
                    await model_provider_repo.get_by_id(session, transaction.provider_id)
                    if transaction.provider_id
                    else None
                )
                if transaction.provider_id and (
                    existing is None or existing.provider_type != OPENAI_CODEX_PROVIDER_TYPE
                ):
                    raise OpenAICodexError("OpenAI Codex 账户不存在")
                if existing is not None:
                    old_credentials = get_openai_codex_credentials(existing, _encryption_service())
                    if old_credentials is None:
                        raise OpenAICodexError("原 OpenAI Codex 注册信息不可用")
                    if old_credentials.subject != credentials.subject:
                        raise OpenAICodexError("重新授权返回了不同的 OpenAI Codex 账户")
                    if old_credentials.client_id != credentials.client_id:
                        raise OpenAICodexError("重新授权不能替换已注册的 client ID")
                    provider = existing
                    provider.name = openai_codex_provider_name(credentials)
                else:
                    provider = await model_provider_repo.create(
                        session=session,
                        name=openai_codex_provider_name(credentials),
                        url=OPENAI_CODEX_API_BASE_URL,
                        api_key_encrypted="",
                        provider_type=OPENAI_CODEX_PROVIDER_TYPE,
                    )
                OpenAICodexCredentialStore(_encryption_service()).write(provider, credentials)
                session.add(provider)
                await save_openai_codex_registration(session, credentials, provider.id)
                await session.commit()
                _TRANSACTION_RESULTS[state] = (
                    transaction.expires_at,
                    OpenAICodexAuthStatusResponse(
                        status="success" if credentials.openai_codex_access_enabled else "error",
                        provider_id=provider.id if credentials.openai_codex_access_enabled else None,
                        registration_id=credentials.client_id,
                    ),
                )
                _IN_FLIGHT_TRANSACTIONS.pop(state, None)
            except Exception:
                await session.rollback()
                raise
    except Exception:
        await session.rollback()
        return await _failed_callback(transaction, "OpenAI Codex 授权失败，请重新开始授权")
    finally:
        async with _PENDING_TRANSACTIONS_LOCK:
            _IN_FLIGHT_TRANSACTIONS.pop(state, None)

    if credentials.openai_codex_access_enabled:
        return True, "OpenAI Codex 已连接，可以关闭此窗口"
    return await _failed_callback(
        transaction, "OpenAI Codex 已登录，但账户未授予直接访问权限",
    )


@router.get("/auth/callback", response_class=HTMLResponse, include_in_schema=False)
async def auth_callback(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HTMLResponse:
    success, message = await _complete_authorization(request.query_params, session)
    return _callback_page(success=success, message=message)


@router.post("/auth/complete", response_model=OpenAICodexAuthStatusResponse)
async def manual_callback(
    request: OpenAICodexManualCallbackRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OpenAICodexAuthStatusResponse:
    await require_agent_settings_unlocked(session)
    async with _PENDING_TRANSACTIONS_LOCK:
        transaction = _PENDING_TRANSACTIONS.get(request.authorization_id)
    if transaction is None or transaction.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=400, detail="授权已过期或已处理，请重新开始授权")
    try:
        parameters = parse_openai_codex_callback(request.callback_url, transaction)
    except OpenAICodexError as exc:
        raise HTTPException(status_code=400, detail="回调链接无效或不属于本次授权") from exc
    success, message = await _complete_authorization(parameters, session)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return await auth_status(request.authorization_id)
