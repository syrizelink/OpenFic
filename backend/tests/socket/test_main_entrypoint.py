import socketio  # type: ignore[import-untyped]

from app.main import app, asgi_app, fastapi_app


def test_default_app_entrypoint_is_socketio_asgi_app() -> None:
    assert app is asgi_app
    assert isinstance(app, socketio.ASGIApp)


def test_background_sse_route_removed() -> None:
    route_paths = {getattr(route, "path", "") for route in fastapi_app.routes}
    assert "/api/v1/background/events" not in route_paths
