"""Deterministic development package snapshots, shared by checker and watcher."""

import io
import os
import stat
import zipfile
from pathlib import Path
from pydantic import ValidationError

from app.plugins.manifest import (
    MAX_PACKAGE_BYTES,
    MAX_EXPANDED_BYTES,
    Manifest,
    safe_path,
)

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


def build_package(root: Path) -> bytes:
    root = root.resolve()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        total = 0
        for index, path in enumerate(source_files(root)):
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


class PackageValidationError(ValueError):
    pass


def extract_package(content: bytes, target: Path) -> Manifest:
    if not content or len(content) > MAX_PACKAGE_BYTES:
        raise PackageValidationError("Package must be between 1 byte and 20 MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            files = [info for info in archive.infolist() if not info.is_dir()]
            if (
                len(archive.infolist()) > 512
                or sum(info.file_size for info in files) > MAX_EXPANDED_BYTES
            ):
                raise PackageValidationError("Package exceeds extraction limits")
            seen: set[str] = set()
            for info in archive.infolist():
                name = safe_path(
                    info.filename.rstrip("/") if info.is_dir() else info.filename
                )
                if (
                    name.casefold() in seen
                    or stat.S_ISLNK(info.external_attr >> 16)
                    or info.flag_bits & 1
                ):
                    raise PackageValidationError(
                        "Duplicate, encrypted or symbolic-link archive entry"
                    )
                seen.add(name.casefold())
                if info.is_dir():
                    continue
                destination = target / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(info))
            if not (target / "plugin.json").exists():
                raise PackageValidationError(
                    "Package must contain plugin.json at the archive root"
                )
            manifest = Manifest.model_validate_json(
                (target / "plugin.json").read_bytes()
            )
            entries = [view.entry for view in manifest.views if view.entry]
            if manifest.backend:
                entries.append(manifest.backend)
            if any(not (target / entry).is_file() for entry in entries):
                raise PackageValidationError("Manifest references a missing entry file")
            return manifest
    except PackageValidationError:
        raise
    except ValidationError as error:
        details = "; ".join(
            ".".join(map(str, item["loc"])) + ": " + item["msg"]
            for item in error.errors(include_input=False)
        )
        raise PackageValidationError("Invalid manifest: " + details) from None
    except (ValueError, OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise PackageValidationError(f"Invalid plugin package: {error}") from error
