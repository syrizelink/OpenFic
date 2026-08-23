import socketio  # type: ignore[import-untyped]

from app.auth import AuthMiddleware
from app.main import app, asgi_app, fastapi_app


def test_default_app_entrypoint_wraps_socketio_asgi_app_with_auth() -> None:
    assert isinstance(app, AuthMiddleware)
    assert app.app is asgi_app
    assert isinstance(asgi_app, socketio.ASGIApp)


def test_background_sse_route_removed() -> None:
    route_paths = {getattr(route, "path", "") for route in fastapi_app.routes}
    assert "/api/v1/background/events" not in route_paths
