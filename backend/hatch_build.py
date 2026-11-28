from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from sys import stderr

try:
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface
except ModuleNotFoundError:  # pragma: no cover - fallback for test runtime without hatchling installed
    class BuildHookInterface:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.root = kwargs.get("root", ".")

        def initialize(self, version: str, build_data: dict[str, object]) -> None:
            return None


def build_frontend_assets(backend_dir: Path, frontend_dir: Path, version: str) -> None:
    target_dir = backend_dir / "frontend"

    if not frontend_dir.exists():
        if (target_dir / "index.html").exists():
            stderr.write(f">>> Reusing packaged frontend assets from {target_dir}\n")
            return
        raise RuntimeError(f"Frontend source directory not found: {frontend_dir}")

    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise RuntimeError("pnpm is required for building the OpenFic frontend but it was not found")

    stderr.write(">>> Building OpenFic frontend\n")
    stderr.write("### pnpm install --frozen-lockfile\n")
    subprocess.run([pnpm, "install", "--frozen-lockfile"], check=True, cwd=frontend_dir)  # noqa: S603

    stderr.write("\n### pnpm build\n")
    env = os.environ.copy()
    env["OPENFIC_BUILD_VERSION"] = version
    subprocess.run([pnpm, "build"], check=True, cwd=frontend_dir, env=env)  # noqa: S603

    dist_dir = frontend_dir / "dist"
    if not (dist_dir / "index.html").exists():
        raise RuntimeError(f"Frontend build did not produce index.html: {dist_dir}")

    shutil.rmtree(target_dir, ignore_errors=True)
    shutil.copytree(dist_dir, target_dir)
    stderr.write(f"\n### copied frontend dist to {target_dir}\n")


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, object]) -> None:
        super().initialize(version, build_data)
        backend_dir = Path(self.root)
        target_dir = backend_dir / "frontend"
        if version == "editable":
            target_dir.mkdir(parents=True, exist_ok=True)
            stderr.write(">>> Skipping frontend build for editable install\n")
            return
        frontend_dir = backend_dir.parent / "frontend"
        build_frontend_assets(backend_dir=backend_dir, frontend_dir=frontend_dir, version=version)
