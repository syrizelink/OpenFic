"""Entri CLI OpenFic.

Dipakai untuk menjalankan layanan lokal setelah dipasang melalui pipx/uvx.
Desktop maupun Docker menjalankan layanan backend melalui entri ini.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys

from app.logging import configure_standard_logging

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000


def _windows_selector_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()


def _get_uvicorn_loop_factory() -> str:
    """Use a selector loop on Windows because pyzmq requires add_reader."""
    if sys.platform == "win32":
        return "app.cli:_windows_selector_loop_factory"
    return "auto"


def _ensure_data_dir() -> None:
    """Direktori data bawaan CLI adalah ~/.openfic, hanya berlaku bila belum diatur eksplisit."""
    if os.getenv("OPENFIC_DATA_DIR"):
        return
    data_dir = Path.home() / ".openfic"
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENFIC_DATA_DIR"] = str(data_dir)


def _read_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("openfic")
    except (PackageNotFoundError, Exception):
        return "0.0.0"


def handle_version(_args: argparse.Namespace) -> None:
    print(f"openfic {_read_version()}")


def handle_serve(args: argparse.Namespace) -> None:
    _ensure_data_dir()
    configure_standard_logging()
    os.environ["OPENFIC_SERVER_HOST"] = args.host
    os.environ["OPENFIC_SERVER_PORT"] = str(args.port)
    auth_password = getattr(args, "auth_password", None)
    if auth_password is not None:
        os.environ["OPENFIC_AUTH_PASSWORD"] = auth_password

    import uvicorn
    from app.main import app as asgi_app, fastapi_app

    config = uvicorn.Config(
        asgi_app,
        host=args.host,
        port=args.port,
        loop=_get_uvicorn_loop_factory(),
        log_level="info",
        log_config=None,
        access_log=False,
    )
    server = uvicorn.Server(config)
    fastapi_app.state.uvicorn_server = server
    server.run()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openfic",
        description="Peluncur layanan lokal OpenFic",
    )

    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Menjalankan layanan lokal")
    serve_parser.add_argument(
        "--host", default=_DEFAULT_HOST, help=f"Alamat bind (bawaan {_DEFAULT_HOST})"
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=_DEFAULT_PORT,
        help=f"Port bind (bawaan {_DEFAULT_PORT})",
    )
    serve_parser.add_argument(
        "--auth-password", default=None, help="Mengaktifkan proteksi kata sandi aplikasi"
    )
    serve_parser.set_defaults(handler=handle_serve)

    version_parser = subparsers.add_parser("version", help="Menampilkan nomor versi")
    version_parser.set_defaults(handler=handle_version)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        raise SystemExit(0)

    handler(args)


if __name__ == "__main__":
    main()
