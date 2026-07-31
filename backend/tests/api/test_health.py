from types import SimpleNamespace

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_shutdown_endpoint_requests_graceful_server_exit(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    server = SimpleNamespace(should_exit=False)
    app.state.uvicorn_server = server
    monkeypatch.setenv("OPENFIC_SHUTDOWN_TOKEN", "desktop-shutdown-token")

    response = await client.post(
        "/api/v1/health/shutdown",
        headers={"X-OpenFic-Shutdown-Token": "desktop-shutdown-token"},
    )

    assert response.status_code == 202
    assert server.should_exit is True


@pytest.mark.asyncio
async def test_shutdown_endpoint_rejects_invalid_token(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    server = SimpleNamespace(should_exit=False)
    app.state.uvicorn_server = server
    monkeypatch.setenv("OPENFIC_SHUTDOWN_TOKEN", "desktop-shutdown-token")

    response = await client.post(
        "/api/v1/health/shutdown",
        headers={"X-OpenFic-Shutdown-Token": "invalid-token"},
    )

    assert response.status_code == 404
    assert server.should_exit is False
