from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.api.routers.auth as auth_router
from app.api.routers.auth import router
from app.api.schemas.setting import SettingsResponse
from app.auth import AuthMiddleware, AuthService
from app.storage.database import get_session
from app.settings import Settings


def _create_auth_test_app(password: str | None, api_prefix: str = "/api/v1") -> AuthMiddleware:
    app = FastAPI()
    auth_service = AuthService(password)
    app.state.auth_service = auth_service
    app.include_router(router, prefix=api_prefix)

    @app.get(f"{api_prefix}/protected")
    async def protected() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{api_prefix}/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/")
    async def frontend() -> dict[str, str]:
        return {"page": "frontend"}

    return AuthMiddleware(app, auth_service, api_prefix)


async def _request(app: AuthMiddleware, method: str, url: str, **kwargs) -> object:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


async def test_auth_disabled_allows_protected_requests() -> None:
    response = await _request(_create_auth_test_app(None), "GET", "/api/v1/protected")

    assert response.status_code == 200


def test_auth_password_can_be_loaded_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENFIC_AUTH_PASSWORD", "secret")

    settings = Settings(_env_file=None)

    assert settings.auth_password == "secret"


async def test_auth_status_reports_enabled_without_exposing_password() -> None:
    response = await _request(_create_auth_test_app("secret"), "GET", "/api/v1/auth/status")

    assert response.status_code == 200
    assert response.json() == {"enabled": True, "authenticated": False}
    assert "secret" not in response.text


async def test_public_preferences_expose_only_interface_preferences(monkeypatch) -> None:
    app = _create_auth_test_app("secret")

    async def fake_get_settings(_session) -> SettingsResponse:
        return SettingsResponse(
            language="en",
            theme="dark",
            font_family="Noto Serif SC Variable",
            code_font_family="JetBrains Mono Variable",
            base_font_size=18,
            editor_font_size=20,
        )

    async def fake_session():
        yield object()

    monkeypatch.setattr(auth_router, "get_settings", fake_get_settings)
    app.app.dependency_overrides[get_session] = fake_session

    response = await _request(app, "GET", "/api/v1/auth/preferences")

    assert response.status_code == 200
    assert response.json() == {
        "language": "en",
        "theme": "dark",
        "font_family": "Noto Serif SC Variable",
        "code_font_family": "JetBrains Mono Variable",
        "base_font_size": 18,
        "editor_font_size": 20,
    }


async def test_auth_blocks_protected_requests_until_login() -> None:
    response = await _request(_create_auth_test_app("secret"), "GET", "/api/v1/protected")

    assert response.status_code == 401


async def test_auth_uses_configured_api_prefix() -> None:
    app = _create_auth_test_app("secret", "/internal")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        protected_response = await client.get("/internal/protected")
        login_response = await client.post(
            "/internal/auth/login",
            json={"password": "secret", "trust_device": False},
        )
        authenticated_response = await client.get("/internal/protected")

    assert protected_response.status_code == 401
    assert login_response.status_code == 200
    assert authenticated_response.status_code == 200


async def test_auth_rejects_wrong_password() -> None:
    response = await _request(
        _create_auth_test_app("secret"),
        "POST",
        "/api/v1/auth/login",
        json={"password": "wrong", "trust_device": False},
    )

    assert response.status_code == 401


async def test_auth_login_allows_session_cookie() -> None:
    app = _create_auth_test_app("secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"password": "secret", "trust_device": False},
        )
        protected_response = await client.get("/api/v1/protected")

    assert login_response.status_code == 200
    assert "Max-Age=2592000" not in login_response.headers["set-cookie"]
    assert protected_response.status_code == 200


async def test_auth_login_trust_device_sets_thirty_day_cookie() -> None:
    app = _create_auth_test_app("secret")
    response = await _request(
        app,
        "POST",
        "/api/v1/auth/login",
        json={"password": "secret", "trust_device": True},
    )

    assert response.status_code == 200
    assert "Max-Age=2592000" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


async def test_auth_keeps_frontend_route_public() -> None:
    response = await _request(_create_auth_test_app("secret"), "GET", "/")

    assert response.status_code == 200


async def test_auth_keeps_health_check_public() -> None:
    response = await _request(_create_auth_test_app("secret"), "GET", "/api/v1/health")

    assert response.status_code == 200


async def test_auth_rejects_websocket_with_unauthorized_response() -> None:
    app = _create_auth_test_app("secret")
    sent_messages: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "websocket.connect"}

    async def send(message: dict[str, object]) -> None:
        sent_messages.append(message)

    await app(
        {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "scheme": "ws",
            "server": ("test", 80),
            "client": ("test", 123),
            "root_path": "",
            "path": "/socket.io/",
            "raw_path": b"/socket.io/",
            "query_string": b"",
            "headers": [],
            "subprotocols": [],
            "state": {},
            "extensions": {"websocket.http.response": {}},
        },
        receive,
        send,
    )

    assert sent_messages[0]["type"] == "websocket.http.response.start"
    assert sent_messages[0]["status"] == 401
