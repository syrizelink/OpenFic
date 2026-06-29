"""OpenFic CLI 入口。

用于以 pipx/uvx 安装后启动本地服务，默认绑定 127.0.0.1 并自动打开浏览器。
桌面端（PyInstaller）与 Docker 不走此入口。
"""

from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path

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


def _schedule_browser(host: str, port: int) -> None:
    def _open() -> None:
        import time
        import urllib.error
        import urllib.request

        url = f"http://{host}:{port}/api/v1/health"
        for _ in range(30):
            try:
                with urllib.request.urlopen(url, timeout=1):
                    break
            except (urllib.error.URLError, OSError, TimeoutError):
                time.sleep(0.5)
        webbrowser.open(f"http://{host}:{port}")

    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="openfic",
        description="OpenFic 本地服务启动器",
    )
    parser.add_argument("--host", default=_DEFAULT_HOST, help=f"绑定地址（默认 {_DEFAULT_HOST}）")
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT, help=f"绑定端口（默认 {_DEFAULT_PORT}）")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    parser.add_argument("--version", action="version", version=f"openfic {_read_version()}")
    args = parser.parse_args()

    _ensure_data_dir()

    if not args.no_browser:
        _schedule_browser(args.host, args.port)

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
