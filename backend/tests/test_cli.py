import sys
import shutil
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

import app.cli as cli
from uvicorn.config import Config


def test_get_uvicorn_loop_factory_uses_selector_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(cli.sys, "platform", "win32")

    assert cli._get_uvicorn_loop_factory() == "app.cli:_windows_selector_loop_factory"


def test_get_uvicorn_loop_factory_uses_default_on_non_windows(monkeypatch) -> None:
    monkeypatch.setattr(cli.sys, "platform", "linux")

    assert cli._get_uvicorn_loop_factory() == "auto"


def test_windows_selector_loop_factory_creates_selector_loop() -> None:
    loop = cli._windows_selector_loop_factory()
    try:
        assert isinstance(loop, cli.asyncio.SelectorEventLoop)
    finally:
        loop.close()


def test_uvicorn_loads_windows_selector_loop_factory() -> None:
    config = Config("app.main:app", loop="app.cli:_windows_selector_loop_factory")
    factory = config.get_loop_factory()
    assert factory is not None
    loop = factory()
    try:
        assert isinstance(loop, cli.asyncio.SelectorEventLoop)
    finally:
        loop.close()


def test_dev_command_loads_windows_selector_loop_factory() -> None:
    justfile = Path(__file__).resolve().parents[1] / "justfile"
    content = justfile.read_text(encoding="utf-8")

    assert 'if os() == "windows"' in content
    assert "--loop app.cli:_windows_selector_loop_factory" in content


def test_handle_serve_passes_loop_factory_to_uvicorn(monkeypatch) -> None:
    uvicorn_config = Mock()
    uvicorn_server = Mock()
    fastapi_app = SimpleNamespace(state=SimpleNamespace())
    monkeypatch.setattr(cli, "_ensure_data_dir", Mock())
    monkeypatch.setattr(cli, "configure_standard_logging", Mock())
    monkeypatch.setattr(
        cli,
        "_get_uvicorn_loop_factory",
        Mock(return_value="app.cli:_windows_selector_loop_factory"),
    )
    monkeypatch.setitem(
        sys.modules,
        "uvicorn",
        SimpleNamespace(
            Config=Mock(return_value=uvicorn_config),
            Server=Mock(return_value=uvicorn_server),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.main",
        SimpleNamespace(app=object(), fastapi_app=fastapi_app),
    )

    cli.handle_serve(type("Args", (), {"host": "127.0.0.1", "port": 8000})())

    assert sys.modules["uvicorn"].Config.call_args.kwargs["loop"] == "app.cli:_windows_selector_loop_factory"
    assert fastapi_app.state.uvicorn_server is uvicorn_server
    uvicorn_server.run.assert_called_once_with()


def test_serve_parser_accepts_auth_password() -> None:
    args = cli.build_parser().parse_args(["serve", "--auth-password", "secret"])

    assert args.auth_password == "secret"


def test_handle_serve_sets_auth_password_environment(monkeypatch) -> None:
    uvicorn_config = Mock()
    uvicorn_server = Mock()
    fastapi_app = SimpleNamespace(state=SimpleNamespace())
    monkeypatch.delenv("OPENFIC_AUTH_PASSWORD", raising=False)
    monkeypatch.setattr(cli, "_ensure_data_dir", Mock())
    monkeypatch.setattr(cli, "configure_standard_logging", Mock())
    monkeypatch.setitem(
        sys.modules,
        "uvicorn",
        SimpleNamespace(
            Config=Mock(return_value=uvicorn_config),
            Server=Mock(return_value=uvicorn_server),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.main",
        SimpleNamespace(app=object(), fastapi_app=fastapi_app),
    )

    cli.handle_serve(
        type(
            "Args",
            (),
            {"host": "127.0.0.1", "port": 8000, "auth_password": "secret"},
        )()
    )

    assert cli.os.environ["OPENFIC_AUTH_PASSWORD"] == "secret"


@pytest.fixture(scope="module")
def cli_database_template(tmp_path_factory):
    """Reuse the empty schema without sharing connections or mutable test data."""
    from sqlalchemy import create_engine
    from sqlmodel import SQLModel
    from tests.model_registry import register_sqlmodel_models

    register_sqlmodel_models()
    path = tmp_path_factory.mktemp("cli-schema") / "template.db"
    required_tables = [SQLModel.metadata.tables[name] for name in (
        "model_providers", "model_provider_oauth_registrations",
    )]
    engine = create_engine(f"sqlite:///{path}")
    try:
        with engine.begin() as connection:
            SQLModel.metadata.create_all(connection, tables=required_tables)
    finally:
        engine.dispose()
    return path


@pytest.mark.parametrize("reauthorize", [False, True])
@pytest.mark.parametrize("first_exchange_fails", [False, True])
def test_openai_codex_cli_auth_keeps_callback_path_and_registration(monkeypatch, tmp_path, cli_database_template, reauthorize, first_exchange_fails):
    import app.models.services.openai_codex_service as plan
    from app.storage import database
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    shutil.copyfile(cli_database_template, tmp_path / "cli.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cli.db'}")

    initialize = AsyncMock()

    async def create_session():
        return AsyncSession(engine, expire_on_commit=False)

    monkeypatch.setattr(database, "init_db", initialize)
    monkeypatch.setattr(database, "create_session", create_session)
    monkeypatch.setattr(database, "close_db", engine.dispose)

    credentials = plan.OpenAICodexCredentials(
        client_id="oaiapp_test", ext_agent_host_id="urn:uuid:11111111-1111-4111-8111-111111111111",
        issuer=plan.OPENAI_CODEX_ISSUER, subject="subject", email="user@example.com",
        id_token="id-token", access_token="access-token", refresh_token="refresh-token",
        token_type="Bearer", expires_at=datetime.now(UTC) + timedelta(hours=1),
        scopes=frozenset(plan.OPENAI_CODEX_SCOPES),
    )
    output = tmp_path / "credential.ofc"
    if reauthorize:
        output.write_text(plan.encrypt_portable_credentials(credentials, "passphrase"))
    monkeypatch.setenv("OPENFIC_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(cli, "getpass", lambda _prompt: "passphrase")
    handlers = []
    server = SimpleNamespace(
        sockets=[SimpleNamespace(getsockname=lambda: ("127.0.0.1", 54321))],
        close=Mock(),
    )

    async def closed():
        return None

    server.wait_closed = closed

    async def start_server(handler, host, port):
        assert host == "127.0.0.1"
        handlers.append(handler)
        return server

    monkeypatch.setattr(cli.asyncio, "start_server", start_server)
    original_wait_for = asyncio.wait_for

    async def bounded_wait_for(awaitable, timeout):
        return await original_wait_for(awaitable, timeout=10 if timeout == 600 else timeout)

    monkeypatch.setattr(cli.asyncio, "wait_for", bounded_wait_for)
    callback_tasks = []
    authorization_requests = []

    def open_browser(url):
        params = parse_qs(urlsplit(url).query)
        redirect = urlsplit(params["redirect_uri"][0])
        assert redirect.path == plan.OPENAI_CODEX_CALLBACK_PATH
        is_returning = reauthorize or bool(authorization_requests)
        assert params["client_id"] == ["oaiapp_test" if is_returning else "dynamic_agent_client"]
        if is_returning and output.exists():
            assert params["id_token_hint"] == ["id-token"]
            assert "agent_name_hint" not in params
        authorization_requests.append(params)
        reader = asyncio.StreamReader()
        query = urlencode({"state": params["state"][0], "code": "code", "client_id": "oaiapp_test"})
        reader.feed_data(f"GET {redirect.path}?{query} HTTP/1.1\r\n".encode())
        reader.feed_eof()
        writer = SimpleNamespace(write=Mock(), drain=closed, close=Mock(), wait_closed=closed)
        callback_tasks.append(asyncio.create_task(handlers[-1](reader, writer)))
        return True

    async def exchange(_self, **kwargs):
        assert kwargs["redirect_uri"].endswith(plan.OPENAI_CODEX_CALLBACK_PATH)
        assert kwargs["client_id"] == "oaiapp_test"
        assert kwargs["code"] == "code"
        if first_exchange_fails and len(authorization_requests) == 1:
            raise plan.OpenAICodexOAuthError("invalid_grant")
        return {}

    async def validated(_self, _payload, **_kwargs):
        return credentials

    monkeypatch.setattr(cli.webbrowser, "open", open_browser)
    monkeypatch.setattr(plan.OpenAICodexOAuthClient, "exchange_code", exchange)
    monkeypatch.setattr(plan.OpenAICodexOAuthClient, "credentials_from_token_response", validated)
    args = cli.build_parser().parse_args([
        "openai-codex", "auth", "--output", str(output),
        *(["--input", str(output)] if reauthorize else []),
    ])
    if first_exchange_fails:
        with pytest.raises(plan.OpenAICodexOAuthError, match="invalid_grant"):
            cli.handle_openai_codex_auth(args)
    else:
        cli.handle_openai_codex_auth(args)
    cli.handle_openai_codex_auth(args)
    assert plan.decrypt_portable_credentials(output.read_text(), "passphrase") == credentials
    assert all(task.done() for task in callback_tasks)
    assert server.close.call_count == 2
    assert initialize.await_count == 2
    assert authorization_requests[1]["client_id"] == ["oaiapp_test"]
    assert authorization_requests[0]["state"] != authorization_requests[1]["state"]
