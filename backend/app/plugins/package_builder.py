"""Shared dependency-free packing rules for the host, CLI and repository scripts."""

import fnmatch
import io
import json
import os
import zipfile
from pathlib import Path, PurePosixPath

MAX_PACKAGE_BYTES = 20 * 1024 * 1024
MAX_EXPANDED_BYTES = 40 * 1024 * 1024


def safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(
            "Plugin paths must be relative and cannot traverse directories"
        )
    return value


IGNORED = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".openfic-dev",
}


def source_files(root: Path):
    def unreadable(error):
        raise error

    # Prune before traversing: node_modules and a live development database can
    # contain thousands of files and must never participate in a polling scan.
    for directory, folders, files in os.walk(root, onerror=unreadable):
        folders[:] = sorted(name for name in folders if name not in IGNORED)
        for name in [*folders, *sorted(files)]:
            path = Path(directory) / name
            if name in IGNORED or path.suffix in {".pyc", ".zip"}:
                continue
            if path.is_symlink():
                raise ValueError(
                    f"Symbolic links are not supported: {path.relative_to(root)}"
                )
            if path.is_file():
                yield path


def package_files(root: Path):
    config = root / "plugin.dev.json"
    options = (
        json.loads(config.read_text()).get("package", {}) if config.exists() else {}
    )
    if not isinstance(options, dict) or set(options) - {"include", "exclude"}:
        raise ValueError("plugin.dev.json package supports include/exclude lists")
    include, exclude = options.get("include", ["**"]), options.get("exclude", [])
    for patterns in (include, exclude):
        if not isinstance(patterns, list) or any(
            not isinstance(p, str) for p in patterns
        ):
            raise ValueError(
                "Package include/exclude must be lists of relative patterns"
            )
        for pattern in patterns:
            safe_path(pattern)

    def matches(name, patterns):
        return any(
            name == p or name.startswith(p + "/") or fnmatch.fnmatchcase(name, p)
            for p in patterns
        )

    if matches("plugin.json", exclude):
        raise ValueError("Cannot exclude plugin.json from a package")
    for path in source_files(root):
        name = path.relative_to(root).as_posix()
        if (
            name == "plugin.json"
            or matches(name, include)
            and not matches(name, exclude)
        ):
            yield path


def build_package(root: Path) -> bytes:
    root = root.resolve()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        total = 0
        for index, path in enumerate(package_files(root)):
            if index >= 512:
                raise ValueError("Package exceeds 512 files")
            total += path.stat().st_size
            if total > 40 * 1024 * 1024:
                raise ValueError("Package exceeds 40 MiB unpacked")
            entry = zipfile.ZipInfo(
                path.relative_to(root).as_posix(), (2026, 1, 1, 0, 0, 0)
            )
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    if output.tell() > MAX_PACKAGE_BYTES:
        raise ValueError("Package exceeds 20 MiB")
    return output.getvalue()
