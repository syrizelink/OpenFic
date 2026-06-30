"""OpenFic CLI 入口。

用于以 pipx/uvx 安装后启动本地服务。
桌面端（PyInstaller）与 Docker 不走此入口。
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.logging import configure_standard_logging

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000


def _ensure_data_dir() -> None:
    """CLI 默认数据目录为 ~/.openfic，仅在未显式设置时生效。"""
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

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
        log_config=None,
        access_log=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openfic",
        description="OpenFic 本地服务启动器",
    )

    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="启动本地服务")
    serve_parser.add_argument("--host", default=_DEFAULT_HOST, help=f"绑定地址（默认 {_DEFAULT_HOST}）")
    serve_parser.add_argument("--port", type=int, default=_DEFAULT_PORT, help=f"绑定端口（默认 {_DEFAULT_PORT}）")
    serve_parser.set_defaults(handler=handle_serve)

    version_parser = subparsers.add_parser("version", help="显示版本号")
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
