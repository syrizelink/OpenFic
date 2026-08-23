"""Application-level password authentication."""

from dataclasses import dataclass
from hmac import compare_digest
from http.cookies import SimpleCookie

from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

AUTH_COOKIE_NAME = "openfic_auth"
AUTH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
_AUTH_COOKIE_SALT = "openfic-auth-cookie"


@dataclass(frozen=True)
class AuthService:
    """Validate the configured shared password and sign login cookies."""

    password: str | None

    @property
    def enabled(self) -> bool:
        return bool(self.password)

    def verify_password(self, candidate: str) -> bool:
        return self.enabled and compare_digest(candidate, self.password or "")

    def create_cookie_value(self) -> str:
        if not self.enabled:
            raise RuntimeError("Authentication is not enabled")
        serializer = URLSafeTimedSerializer(self.password or "", salt=_AUTH_COOKIE_SALT)
        return serializer.dumps("authenticated")

    def verify_cookie_value(self, value: str | None) -> bool:
        if not self.enabled or not value:
            return False

        serializer = URLSafeTimedSerializer(self.password or "", salt=_AUTH_COOKIE_SALT)
        try:
            return serializer.loads(value, max_age=AUTH_COOKIE_MAX_AGE) == "authenticated"
        except BadSignature:
            return False


class AuthMiddleware:
    """Protect backend resources while leaving the frontend shell public."""

    _STATIC_PROTECTED_PREFIXES = (
        "/socket.io",
        "/icons/",
        "/covers/",
        "/character-images/",
        "/agent-attachments/",
        "/docs",
        "/redoc",
        "/openapi.json",
    )

    def __init__(self, app: ASGIApp, auth_service: AuthService, api_prefix: str) -> None:
        self.app = app
        self.auth_service = auth_service
        self.api_prefix = api_prefix.rstrip("/")
        self._protected_prefixes = (
            f"{self.api_prefix}/",
            *self._STATIC_PROTECTED_PREFIXES,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.auth_service.enabled or scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http" and scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith(f"{self.api_prefix}/auth/") or path in {
            f"{self.api_prefix}/health",
            f"{self.api_prefix}/health/shutdown",
        } or not path.startswith(self._protected_prefixes):
            await self.app(scope, receive, send)
            return

        if self._has_valid_cookie(scope):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await self._reject_websocket(scope, send)
            return

        response = JSONResponse(
            {"detail": "Authentication required"},
            status_code=401,
            headers={"WWW-Authenticate": "Cookie"},
        )
        await response(scope, receive, send)

    async def _reject_websocket(self, scope: Scope, send: Send) -> None:
        if "websocket.http.response" not in (scope.get("extensions") or {}):
            await send({"type": "websocket.close", "code": 1008})
            return

        body = b'{"detail":"Authentication required"}'
        await send(
            {
                "type": "websocket.http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"www-authenticate", b"Cookie"),
                    (b"x-openfic-auth", b"required"),
                ],
            }
        )
        await send({"type": "websocket.http.response.body", "body": body})

    def _has_valid_cookie(self, scope: Scope) -> bool:
        cookie_header = Headers(scope=scope).get("cookie")
        if not cookie_header:
            return False

        cookies = SimpleCookie()
        cookies.load(cookie_header)
        cookie = cookies.get(AUTH_COOKIE_NAME)
        return self.auth_service.verify_cookie_value(cookie.value if cookie else None)
