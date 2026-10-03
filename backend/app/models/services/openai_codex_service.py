"""Sign in with OpenAI Codex credentials and token lifecycle management."""

from __future__ import annotations

import asyncio
import base64
from binascii import Error as Base64Error
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import secrets
import uuid
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
import jwt.algorithms
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.settings import BACKEND_DATA_DIR, settings
from app.storage.database import create_session

if TYPE_CHECKING:
    from app.models.entities.model_provider import ModelProvider
    from app.models.entities.model_provider_oauth_registration import ModelProviderOAuthRegistration


OPENAI_CODEX_PROVIDER_TYPE = "openai-codex"
OPENAI_CODEX_API_BASE_URL = "https://api.openai.com/v1"
OPENAI_CODEX_ISSUER = "https://auth.openai.com"
OPENAI_CODEX_AUTHORIZATION_ENDPOINT = (
    "https://auth.openai.com/api/accounts/authorize"
)
OPENAI_CODEX_TOKEN_ENDPOINT = "https://auth.openai.com/api/accounts/oauth/token"
OPENAI_CODEX_JWKS_URI = "https://auth.openai.com/.well-known/jwks.json"
OPENAI_CODEX_RESOURCE = OPENAI_CODEX_API_BASE_URL
OPENAI_CODEX_DYNAMIC_CLIENT_ID = "dynamic_agent_client"
OPENAI_CODEX_AGENT_NAME = "OpenFic"
OPENAI_CODEX_SCOPES = (
    "openid",
    "profile",
    "email",
    "offline_access",
    "resource.invoke",
    "chatgpt.tokens.use.direct",
)
OPENAI_CODEX_REQUIRED_SCOPE = "chatgpt.tokens.use.direct"
OPENAI_CODEX_CALLBACK_PATH = "/api/v1/openai-codex/auth/callback"
OPENAI_CODEX_TOKEN_REFRESH_LEEWAY = timedelta(seconds=60)
OPENAI_CODEX_TRANSACTION_TTL = timedelta(minutes=10)

_REFRESH_LOCKS: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_JWKS_CACHE: dict[str, dict[str, Any]] = {}
_JWKS_LOCK = asyncio.Lock()


class OpenAICodexError(RuntimeError):
    """Base error for OpenAI Codex authentication and inference state."""


class OpenAICodexOAuthError(OpenAICodexError):
    """OAuth authorization or token exchange failed."""


class OpenAICodexReauthorizationRequired(OpenAICodexError):
    """The saved registration needs a new authorization flow."""


class OpenAICodexScopeError(OpenAICodexError):
    """The account did not grant direct OpenAI Codex usage."""


class OpenAICodexAPIError(OpenAICodexError):
    """The direct OpenAI API returned a structured or HTTP error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        param: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.param = param
        self.request_id = request_id


@dataclass(frozen=True)
class OpenAICodexCredentials:
    """Encrypted-at-rest credential payload for one issued client registration."""

    client_id: str
    ext_agent_host_id: str
    issuer: str
    subject: str
    email: str | None
    id_token: str | None
    access_token: str | None
    refresh_token: str | None
    token_type: str
    expires_at: datetime | None
    scopes: frozenset[str]
    earliest_refresh_at: datetime | None = None

    @property
    def openai_codex_access_enabled(self) -> bool:
        return OPENAI_CODEX_REQUIRED_SCOPE in self.scopes

    @property
    def is_connected(self) -> bool:
        return bool(self.access_token and self.refresh_token)

    def has_fresh_access_token(self, now: datetime | None = None) -> bool:
        if not self.access_token or self.expires_at is None:
            return False
        current = now or datetime.now(UTC)
        refresh_at = self.earliest_refresh_at
        if refresh_at is not None and current < refresh_at and current < self.expires_at:
            return True
        return current + OPENAI_CODEX_TOKEN_REFRESH_LEEWAY < self.expires_at

    def without_tokens(self) -> "OpenAICodexCredentials":
        return replace(
            self,
            id_token=None,
            access_token=None,
            refresh_token=None,
            expires_at=None,
            earliest_refresh_at=None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "ext_agent_host_id": self.ext_agent_host_id,
            "issuer": self.issuer,
            "subject": self.subject,
            "email": self.email,
            "id_token": self.id_token,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "scopes": sorted(self.scopes),
            "earliest_refresh_at": (
                self.earliest_refresh_at.isoformat()
                if self.earliest_refresh_at
                else None
            ),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OpenAICodexCredentials":
        required = ("client_id", "ext_agent_host_id", "issuer", "subject")
        if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
            raise ValueError("OpenAI Codex credential metadata is incomplete")

        def parse_datetime(value: Any) -> datetime | None:
            if not isinstance(value, str) or not value:
                return None
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        raw_scopes = payload.get("scopes", [])
        if isinstance(raw_scopes, str):
            raw_scopes = raw_scopes.split()
        if not isinstance(raw_scopes, list) or not all(
            isinstance(item, str) for item in raw_scopes
        ):
            raise ValueError("OpenAI Codex credential scopes are invalid")
        scopes: list[str] = raw_scopes
        raw_token_type = payload.get("token_type")
        token_type = raw_token_type if isinstance(raw_token_type, str) else "Bearer"

        return cls(
            client_id=payload["client_id"],
            ext_agent_host_id=payload["ext_agent_host_id"],
            issuer=payload["issuer"],
            subject=payload["subject"],
            email=payload.get("email") if isinstance(payload.get("email"), str) else None,
            id_token=payload.get("id_token") if isinstance(payload.get("id_token"), str) else None,
            access_token=(
                payload.get("access_token")
                if isinstance(payload.get("access_token"), str)
                else None
            ),
            refresh_token=(
                payload.get("refresh_token")
                if isinstance(payload.get("refresh_token"), str)
                else None
            ),
            token_type=token_type,
            expires_at=parse_datetime(payload.get("expires_at")),
            scopes=frozenset(scopes),
            earliest_refresh_at=parse_datetime(payload.get("earliest_refresh_at")),
        )

    @classmethod
    def from_json(cls, value: str) -> "OpenAICodexCredentials":
        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise ValueError("OpenAI Codex credential payload must be an object")
        return cls.from_dict(payload)


def openai_codex_provider_name(credentials: OpenAICodexCredentials) -> str:
    account_label = credentials.email or credentials.client_id[-8:]
    return f"OpenAI Codex ({account_label}, {credentials.client_id[-8:]})"


@dataclass(frozen=True)
class OpenAICodexOAuthTransaction:
    state: str
    nonce: str
    code_verifier: str
    code_challenge: str
    redirect_uri: str
    expected_client_id: str
    ext_agent_host_id: str
    provider_id: str | None
    id_token_hint: str | None
    login_hint: str | None
    expires_at: datetime
    expected_subject: str | None = None


def parse_openai_codex_callback(
    callback_url: str, transaction: OpenAICodexOAuthTransaction
) -> dict[str, str]:
    try:
        value = callback_url.strip()
        if any(character.isspace() for character in value):
            raise ValueError
        actual = urlsplit(value)
        expected = urlsplit(transaction.redirect_uri)
        if (
            actual.scheme != expected.scheme
            or actual.netloc != expected.netloc
            or actual.path != expected.path
            or actual.fragment
            or actual.username
            or actual.password
        ):
            raise ValueError
        query = parse_qs(actual.query, keep_blank_values=True, max_num_fields=20)
        if any(len(values) != 1 for values in query.values()):
            raise ValueError
        parameters = {key: values[0] for key, values in query.items()}
        if parameters.get("state") != transaction.state:
            raise ValueError
        if not parameters.get("code") and not parameters.get("error"):
            raise ValueError
        return parameters
    except ValueError as exc:
        raise OpenAICodexOAuthError("回调链接无效或不属于本次授权") from exc


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_urlsafe_value(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def _build_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
    ext_agent_host_id: str,
    agent_name_hint: str | None = None,
    id_token_hint: str | None = None,
    login_hint: str | None = None,
) -> str:
    if not redirect_uri.startswith("http://127.0.0.1:"):
        raise ValueError("OpenAI Codex OAuth must use a 127.0.0.1 loopback redirect")
    params: dict[str, str] = {
        "client_id": client_id,
        "ext_agent_host_id": ext_agent_host_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(OPENAI_CODEX_SCOPES),
        "resource": OPENAI_CODEX_RESOURCE,
        "state": state,
        "nonce": nonce,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
    }
    if agent_name_hint:
        params["agent_name_hint"] = agent_name_hint
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    if login_hint:
        params["login_hint"] = login_hint
    return f"{OPENAI_CODEX_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


def get_openai_codex_host_id(data_dir: Path | None = None) -> str:
    directory = data_dir or BACKEND_DATA_DIR
    path = directory / "openai-codex-host-id"
    try:
        value = path.read_text(encoding="utf-8").strip()
        parsed = uuid.UUID(value.removeprefix("urn:uuid:"))
        if parsed.version == 4:
            return f"urn:uuid:{parsed}"
    except (OSError, ValueError):
        pass

    directory.mkdir(parents=True, exist_ok=True)
    value = f"urn:uuid:{uuid.uuid4()}"
    try:
        file_descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
            file.write(value)
        return value
    except FileExistsError:
        try:
            existing = path.read_text(encoding="utf-8").strip()
            parsed = uuid.UUID(existing.removeprefix("urn:uuid:"))
            if parsed.version == 4:
                return f"urn:uuid:{parsed}"
        except (OSError, ValueError):
            pass

    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary_path.write_text(value, encoding="utf-8")
    temporary_path.chmod(0o600)
    temporary_path.replace(path)
    path.chmod(0o600)
    return value


async def _load_jwks(*, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    async with _JWKS_LOCK:
        if _JWKS_CACHE and not force_refresh:
            return dict(_JWKS_CACHE)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(OPENAI_CODEX_JWKS_URI)
            response.raise_for_status()
            payload = response.json()
        keys = payload.get("keys") if isinstance(payload, dict) else None
        if not isinstance(keys, list):
            raise OpenAICodexOAuthError("OpenAI JWKS 响应格式无效")
        _JWKS_CACHE.clear()
        _JWKS_CACHE.update(
            {
                item["kid"]: item
                for item in keys
                if isinstance(item, dict) and isinstance(item.get("kid"), str)
            }
        )
        return dict(_JWKS_CACHE)


async def verify_openai_codex_id_token(
    id_token: str,
    *,
    client_id: str,
    nonce: str,
) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.InvalidTokenError as exc:
        raise OpenAICodexOAuthError("ID token header 无效") from exc

    kid = header.get("kid")
    algorithm = header.get("alg")
    if not isinstance(kid, str) or not isinstance(algorithm, str):
        raise OpenAICodexOAuthError("ID token 缺少签名元数据")
    keys = await _load_jwks()
    jwk = keys.get(kid)
    if jwk is None:
        keys = await _load_jwks(force_refresh=True)
        jwk = keys.get(kid)
    if jwk is None or jwk.get("alg") not in {algorithm, None}:
        raise OpenAICodexOAuthError("ID token 签名密钥未知")
    if algorithm not in {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}:
        raise OpenAICodexOAuthError("ID token 签名算法不受支持")

    try:
        key_algorithm = jwt.algorithms.get_default_algorithms()[algorithm]
        signing_key = key_algorithm.from_jwk(json.dumps(jwk))
        claims = jwt.decode(
            id_token,
            signing_key,
            algorithms=[algorithm],
            audience=client_id,
            issuer=OPENAI_CODEX_ISSUER,
            options={"require": ["sub", "iat", "exp"]},
            leeway=5,
        )
    except jwt.InvalidTokenError as exc:
        raise OpenAICodexOAuthError("ID token 验证失败") from exc

    if claims.get("nonce") != nonce:
        raise OpenAICodexOAuthError("ID token nonce 不匹配")
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise OpenAICodexOAuthError("ID token 缺少 subject")
    return claims


class OpenAICodexOAuthClient:
    """Build and validate the public-client PKCE flow."""

    def create_transaction(
        self,
        *,
        redirect_uri: str,
        ext_agent_host_id: str,
        expected_client_id: str = OPENAI_CODEX_DYNAMIC_CLIENT_ID,
        provider_id: str | None = None,
        id_token_hint: str | None = None,
        login_hint: str | None = None,
        expected_subject: str | None = None,
    ) -> OpenAICodexOAuthTransaction:
        verifier = _new_urlsafe_value(64)
        return OpenAICodexOAuthTransaction(
            state=_new_urlsafe_value(),
            nonce=_new_urlsafe_value(),
            code_verifier=verifier,
            code_challenge=_build_code_challenge(verifier),
            redirect_uri=redirect_uri,
            expected_client_id=expected_client_id,
            ext_agent_host_id=ext_agent_host_id,
            provider_id=provider_id,
            id_token_hint=id_token_hint,
            login_hint=login_hint,
            expires_at=_utc_now() + OPENAI_CODEX_TRANSACTION_TTL,
            expected_subject=expected_subject,
        )

    def authorization_url(self, transaction: OpenAICodexOAuthTransaction) -> str:
        is_initial_registration = (
            transaction.expected_client_id == OPENAI_CODEX_DYNAMIC_CLIENT_ID
        )
        return build_authorization_url(
            client_id=transaction.expected_client_id,
            redirect_uri=transaction.redirect_uri,
            state=transaction.state,
            nonce=transaction.nonce,
            code_challenge=transaction.code_challenge,
            ext_agent_host_id=transaction.ext_agent_host_id,
            agent_name_hint=OPENAI_CODEX_AGENT_NAME if is_initial_registration else None,
            id_token_hint=transaction.id_token_hint,
            login_hint=transaction.login_hint,
        )

    def validate_callback_client_id(
        self,
        *,
        returned_client_id: str | None,
        expected_client_id: str,
    ) -> str:
        if expected_client_id == OPENAI_CODEX_DYNAMIC_CLIENT_ID:
            if not returned_client_id or returned_client_id == OPENAI_CODEX_DYNAMIC_CLIENT_ID:
                raise ValueError("new registration callback did not return an issued client ID")
            return returned_client_id
        if returned_client_id and returned_client_id != expected_client_id:
            raise ValueError("OAuth callback returned a different client ID")
        return expected_client_id

    async def exchange_code(
        self,
        *,
        code: str,
        client_id: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENAI_CODEX_TOKEN_ENDPOINT,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "code_verifier": code_verifier,
                    "redirect_uri": redirect_uri,
                    "resource": OPENAI_CODEX_RESOURCE,
                },
            )
            if not response.is_success:
                raise OpenAICodexOAuthError(_oauth_error_message(response))
            payload = response.json()
        if not isinstance(payload, dict):
            raise OpenAICodexOAuthError("OAuth token 响应格式无效")
        return payload

    async def credentials_from_token_response(
        self,
        payload: dict[str, Any],
        *,
        client_id: str,
        nonce: str,
        ext_agent_host_id: str,
    ) -> OpenAICodexCredentials:
        id_token = payload.get("id_token")
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        if (
            not isinstance(id_token, str)
            or not id_token
            or not isinstance(access_token, str)
            or not access_token
            or not isinstance(refresh_token, str)
            or not refresh_token
        ):
            raise OpenAICodexOAuthError("OAuth token 响应缺少必要凭据")
        claims = await verify_openai_codex_id_token(
            id_token,
            client_id=client_id,
            nonce=nonce,
        )
        raw_scopes = payload.get("scope") or ""
        scopes = frozenset(raw_scopes.split()) if isinstance(raw_scopes, str) else frozenset()
        expires_in = payload.get("expires_in", 3600)
        if not isinstance(expires_in, int) or expires_in <= 0:
            expires_in = 3600
        earliest_refresh_at = payload.get("earliest_refresh_at")
        earliest_refresh = (
            datetime.fromtimestamp(earliest_refresh_at, UTC)
            if isinstance(earliest_refresh_at, (int, float))
            else None
        )
        return OpenAICodexCredentials(
            client_id=client_id,
            ext_agent_host_id=ext_agent_host_id,
            issuer=OPENAI_CODEX_ISSUER,
            subject=claims["sub"],
            email=claims.get("email") if isinstance(claims.get("email"), str) else None,
            id_token=id_token,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=(
                payload["token_type"]
                if isinstance(payload.get("token_type"), str)
                else "Bearer"
            ),
            expires_at=_utc_now() + timedelta(seconds=expires_in),
            scopes=scopes,
            earliest_refresh_at=earliest_refresh,
        )


def _oauth_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        code = payload.get("error") or payload.get("code")
        description = payload.get("error_description") or payload.get("detail")
        if isinstance(code, str) and isinstance(description, str):
            return f"OAuth 请求失败: {code}: {description}"
        if isinstance(code, str):
            return f"OAuth 请求失败: {code}"
    return f"OAuth 请求失败: HTTP {response.status_code}"


class OpenAICodexCredentialStore:
    """Persist encrypted credentials and serialize refreshes per registration."""

    def __init__(self, encryption_service: EncryptionService):
        self.encryption_service = encryption_service

    def read(self, provider: ModelProvider) -> OpenAICodexCredentials:
        if provider.provider_type != OPENAI_CODEX_PROVIDER_TYPE:
            raise ValueError("provider is not a OpenAI Codex provider")
        if not provider.credentials_encrypted:
            raise OpenAICodexReauthorizationRequired("OpenAI Codex 需要重新授权")
        try:
            return OpenAICodexCredentials.from_json(
                self.encryption_service.decrypt(provider.credentials_encrypted)
            )
        except Exception as exc:
            raise OpenAICodexReauthorizationRequired("OpenAI Codex 凭据无法解密") from exc

    def write(self, provider: ModelProvider, credentials: OpenAICodexCredentials) -> None:
        provider.credentials_encrypted = self.encryption_service.encrypt(credentials.to_json())
        provider.api_key_encrypted = ""
        provider.url = OPENAI_CODEX_API_BASE_URL

    async def get_access_token(self, provider_id: str) -> str:
        from app.models.repos import model_provider_repo

        async with _REFRESH_LOCKS[provider_id]:
            session = await create_session()
            try:
                provider = await model_provider_repo.get_by_id(session, provider_id)
                if provider is None:
                    raise OpenAICodexReauthorizationRequired("OpenAI Codex 提供商不存在")
                credentials = self.read(provider)
                if not credentials.openai_codex_access_enabled:
                    raise OpenAICodexScopeError("OpenAI Codex 使用权限未授予")
                if credentials.has_fresh_access_token():
                    return credentials.access_token or ""

                credentials = await self._refresh_with_database_lock(
                    session,
                    provider_id,
                )
                if not credentials.access_token:
                    raise OpenAICodexReauthorizationRequired("OpenAI Codex 需要重新授权")
                return credentials.access_token
            finally:
                await session.close()

    async def _refresh_with_database_lock(
        self,
        session: AsyncSession,
        provider_id: str,
    ) -> OpenAICodexCredentials:
        from app.models.repos import model_provider_repo

        await self._lock_session(session)

        provider = await model_provider_repo.get_by_id(session, provider_id)
        if provider is None:
            raise OpenAICodexReauthorizationRequired("OpenAI Codex 提供商不存在")
        credentials = self.read(provider)
        if credentials.has_fresh_access_token():
            await session.commit()
            return credentials
        if not credentials.refresh_token:
            raise OpenAICodexReauthorizationRequired("OpenAI Codex refresh token 已失效")

        try:
            payload = await self._refresh_token(credentials)
        except OpenAICodexOAuthError as exc:
            if _is_terminal_refresh_error(str(exc)):
                cleared = credentials.without_tokens()
                self.write(provider, cleared)
                await session.commit()
                raise OpenAICodexReauthorizationRequired(
                    "OpenAI Codex refresh token 已失效，请重新授权"
                ) from exc
            await session.rollback()
            raise

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            await session.rollback()
            raise OpenAICodexOAuthError("刷新响应缺少 access_token")
        expires_in = payload.get("expires_in", 3600)
        if not isinstance(expires_in, int) or expires_in <= 0:
            expires_in = 3600
        replacement_refresh_token = payload.get("refresh_token")
        if not isinstance(replacement_refresh_token, str) or not replacement_refresh_token:
            replacement_refresh_token = credentials.refresh_token
        raw_scope = payload.get("scope")
        scopes = (
            frozenset(raw_scope.split())
            if isinstance(raw_scope, str)
            else credentials.scopes
        )
        raw_earliest_refresh_at = payload.get("earliest_refresh_at")
        earliest_refresh_at = (
            datetime.fromtimestamp(raw_earliest_refresh_at, UTC)
            if isinstance(raw_earliest_refresh_at, (int, float))
            else None
        )
        refreshed = replace(
            credentials,
            access_token=access_token,
            refresh_token=replacement_refresh_token,
            token_type=payload.get("token_type")
            if isinstance(payload.get("token_type"), str)
            else credentials.token_type,
            expires_at=_utc_now() + timedelta(seconds=expires_in),
            scopes=scopes,
            earliest_refresh_at=earliest_refresh_at,
        )
        self.write(provider, refreshed)
        await session.commit()
        if not refreshed.openai_codex_access_enabled:
            raise OpenAICodexScopeError("OpenAI Codex 使用权限未授予")
        return refreshed

    async def _lock_session(self, session: AsyncSession) -> None:
        if session.get_bind().dialect.name == "sqlite":
            await session.rollback()
            await session.execute(text("BEGIN IMMEDIATE"))

    async def _refresh_token(self, credentials: OpenAICodexCredentials) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENAI_CODEX_TOKEN_ENDPOINT,
                data={
                    "grant_type": "refresh_token",
                    "client_id": credentials.client_id,
                    "refresh_token": credentials.refresh_token,
                    "resource": OPENAI_CODEX_RESOURCE,
                },
            )
        if not response.is_success:
            raise OpenAICodexOAuthError(_oauth_error_message(response))
        payload = response.json()
        if not isinstance(payload, dict):
            raise OpenAICodexOAuthError("刷新响应格式无效")
        return payload

    async def list_registrations(self, session: AsyncSession) -> list[ModelProviderOAuthRegistration]:
        from app.models.repos import model_provider_oauth_registration_repo, model_provider_repo

        for provider in await model_provider_repo.get_all(session):
            if provider.provider_type != OPENAI_CODEX_PROVIDER_TYPE or not provider.credentials_encrypted:
                continue
            try:
                credentials = self.read(provider)
            except OpenAICodexError:
                continue
            await save_openai_codex_registration(session, credentials, provider.id)
        await session.commit()
        return await model_provider_oauth_registration_repo.get_all(
            session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer=OPENAI_CODEX_ISSUER,
        )

    async def revoke_and_delete(self, session: AsyncSession, provider: ModelProvider) -> bool:
        from app.core.errors import NotFoundError
        from app.models.repos import model_provider_oauth_registration_repo, model_provider_repo

        provider_id = provider.id
        async with _REFRESH_LOCKS[provider_id]:
            await self._lock_session(session)
            current = await model_provider_repo.get_by_id(session, provider_id)
            if current is None:
                raise NotFoundError(f"Provider with id {provider_id} not found")
            confirmed = True
            if current.credentials_encrypted:
                try:
                    credentials = self.read(current)
                except OpenAICodexError:
                    confirmed = False
                else:
                    await save_openai_codex_registration(session, credentials, None)
                    if credentials.refresh_token:
                        confirmed = await self._revoke_refresh_token(credentials)
            registration = await model_provider_oauth_registration_repo.get_for_provider(
                session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer=OPENAI_CODEX_ISSUER, provider_id=provider_id,
            )
            if registration is not None:
                registration.provider_id = None
                session.add(registration)
            if not await model_provider_repo.delete_by_id(session, provider_id):
                raise NotFoundError(f"Provider with id {provider_id} not found")
            await session.commit()
            return confirmed

    async def _revoke_refresh_token(self, credentials: OpenAICodexCredentials) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                discovery = await client.get(
                    "https://auth.openai.com/.well-known/openid-configuration"
                )
                discovery.raise_for_status()
                payload = discovery.json()
                if not isinstance(payload, dict):
                    return False
                endpoint = payload.get("revocation_endpoint")
                if not isinstance(endpoint, str) or not endpoint:
                    return False
                for attempt in range(3):
                    response = await client.post(
                        endpoint,
                        data={
                            "token": credentials.refresh_token,
                            "token_type_hint": "refresh_token",
                            "client_id": credentials.client_id,
                        },
                    )
                    if response.status_code == 200:
                        return True
                    if response.status_code < 500:
                        return False
                    if attempt < 2:
                        await asyncio.sleep(2**attempt)
        except (httpx.HTTPError, ValueError):
            logger.warning("OpenAI Codex remote revocation was not confirmed")
        return False


def get_openai_codex_credentials(
    provider: ModelProvider,
    encryption_service: EncryptionService | None = None,
) -> OpenAICodexCredentials | None:
    if provider.provider_type != OPENAI_CODEX_PROVIDER_TYPE or not provider.credentials_encrypted:
        return None
    try:
        service = OpenAICodexCredentialStore(
            encryption_service or EncryptionService(settings.encryption_key)
        )
        return service.read(provider)
    except OpenAICodexError:
        return None


async def save_openai_codex_registration(
    session: AsyncSession, credentials: OpenAICodexCredentials, provider_id: str | None,
) -> ModelProviderOAuthRegistration:
    from app.models.repos import model_provider_oauth_registration_repo

    if credentials.issuer != OPENAI_CODEX_ISSUER:
        raise OpenAICodexOAuthError("OpenAI Codex OAuth 注册的签发方不匹配")
    return await model_provider_oauth_registration_repo.save_verified(
        session, provider_type=OPENAI_CODEX_PROVIDER_TYPE, issuer=OPENAI_CODEX_ISSUER,
        client_id=credentials.client_id, subject=credentials.subject, email=credentials.email, provider_id=provider_id,
    )


async def get_openai_codex_access_token(provider_id: str) -> str:
    return await OpenAICodexCredentialStore(
        EncryptionService(settings.encryption_key)
    ).get_access_token(provider_id)


def _is_terminal_refresh_error(message: str) -> bool:
    return any(
        code in message
        for code in (
            "invalid_grant",
            "invalid_refresh_token",
            "token_expired",
            "refresh_token_expired",
            "refresh_token_invalidated",
            "refresh_token_reused",
        )
    )


def _passphrase_fernet(passphrase: str, salt: bytes) -> Fernet:
    digest = hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_portable_credentials(
    credentials: OpenAICodexCredentials,
    passphrase: str,
) -> str:
    salt = os.urandom(16)
    ciphertext = _passphrase_fernet(passphrase, salt).encrypt(credentials.to_json().encode())
    return json.dumps(
        {
            "version": 2,
            "salt": base64.urlsafe_b64encode(salt).decode("ascii"),
            "ciphertext": ciphertext.decode("ascii"),
        },
        ensure_ascii=True,
        sort_keys=True,
    )


def decrypt_portable_credentials(value: str, passphrase: str) -> OpenAICodexCredentials:
    try:
        payload = json.loads(value)
        if (
            payload.get("version") != 2
            or not isinstance(payload.get("salt"), str)
            or not isinstance(payload.get("ciphertext"), str)
        ):
            raise ValueError
        salt = base64.urlsafe_b64decode(payload["salt"])
        if len(salt) != 16:
            raise ValueError
        plaintext = _passphrase_fernet(passphrase, salt).decrypt(
            payload["ciphertext"].encode()
        )
        return OpenAICodexCredentials.from_json(plaintext.decode())
    except (Base64Error, InvalidToken, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("OpenAI Codex 凭据文件或口令无效") from exc
