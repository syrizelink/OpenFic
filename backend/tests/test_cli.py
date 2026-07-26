import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

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
    uvicorn_run = Mock()
    monkeypatch.setattr(cli, "_ensure_data_dir", Mock())
    monkeypatch.setattr(cli, "configure_standard_logging", Mock())
    monkeypatch.setattr(
        cli,
        "_get_uvicorn_loop_factory",
        Mock(return_value="app.cli:_windows_selector_loop_factory"),
    )
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=uvicorn_run))

    cli.handle_serve(type("Args", (), {"host": "127.0.0.1", "port": 8000})())

    assert uvicorn_run.call_args.kwargs["loop"] == "app.cli:_windows_selector_loop_factory"
