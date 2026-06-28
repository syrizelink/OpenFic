"""PyInstaller 打包入口。

Electron 壳通过 spawn 本可执行文件拉起后端服务。
环境变量由 Electron 注入（端口、数据目录）；frozen 模式下自动解析内置资源路径。
"""

from __future__ import annotations

import os
import sys


def _setup_frozen_env() -> None:
    """frozen（PyInstaller）模式下设置内置资源路径。"""
    if not getattr(sys, "frozen", False):
        return

    meipass = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    os.environ.setdefault("OPENFIC_FRONTEND_DIST", os.path.join(meipass, "app", "frontend_dist"))
    os.environ.setdefault("OPENFIC_ALEMBIC_INI", os.path.join(meipass, "alembic.ini"))


def main() -> None:
    _setup_frozen_env()

    host = os.environ.get("OPENFIC_HOST", "127.0.0.1")
    port = int(os.environ.get("OPENFIC_PORT", "8000"))

    import uvicorn
    from app.main import app

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
