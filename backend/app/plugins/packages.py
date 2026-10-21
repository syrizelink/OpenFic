"""Deterministic development package snapshots, shared by checker and watcher."""

import io
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

# Public aliases keep existing callers on the shared standard-library packager.
from app.plugins.package_builder import (
    IGNORED as IGNORED,
    source_files as source_files,
    build_package as build_package,
)


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
            if manifest.entry:
                entries.append(manifest.entry)
            if any(not (target / entry).is_file() for entry in entries):
                raise PackageValidationError("Manifest references a missing entry file")
            if not manifest._legacy_resources and any(
                not (target / root).exists() for root in manifest.resources
            ):
                raise PackageValidationError(
                    "Manifest references a missing public resource"
                )
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
