"""Deterministic development package snapshots, shared by checker and watcher."""

import base64
import binascii
import io
import re
import stat
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image
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


def _valid_raster(data: bytes, expected: str) -> bool:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != expected:
                return False
            image.verify()
        return True
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return False


def _local_svg_reference(value: str) -> bool:
    value = value.strip().strip("\"'")
    if value.startswith("#") and len(value) > 1:
        return True
    match = re.fullmatch(
        r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)", value, re.IGNORECASE
    )
    if not match:
        return False
    try:
        data = base64.b64decode(re.sub(r"\s+", "", match.group(2)), validate=True)
    except (binascii.Error, ValueError):
        return False
    return _valid_raster(
        data, {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[match.group(1).lower()]
    )


def _valid_svg_style(value: str, *, css: bool = False) -> bool:
    value = re.sub(r"/\*.*?\*/", "", value, flags=re.DOTALL)
    if "\\" in value or "/*" in value:
        return False
    if css and any(
        rule.lower() not in {"media", "supports", "keyframes"}
        for rule in re.findall(r"@([\w-]+)", value)
    ):
        return False
    if re.search(r"\b(?:image-set|image|src)\s*\(", value, re.IGNORECASE):
        return False
    for match in re.finditer(r"url\s*\(([^)]*)\)", value, re.IGNORECASE):
        if not _local_svg_reference(match.group(1)):
            return False
    return True


def _valid_svg(data: bytes) -> bool:
    try:
        text = data.decode(
            "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        )
        if re.search(r"<!\s*(?:doctype|entity)|<\?xml-stylesheet", text, re.IGNORECASE):
            return False
        root = ElementTree.fromstring(text)
    except (UnicodeError, ElementTree.ParseError, ValueError):
        return False
    if root.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
        return False
    blocked = {
        "script",
        "foreignobject",
        "iframe",
        "object",
        "embed",
        "discard",
    }
    for element in root.iter():
        if element.tag.startswith("{") and not element.tag.startswith(
            "{http://www.w3.org/2000/svg}"
        ):
            return False
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag in blocked:
            return False
        if tag in {"animate", "animatemotion", "animatetransform", "set"}:
            target = element.attrib.get("attributeName", "").lower().rsplit(":", 1)[-1]
            if target in {"href", "src", "style", "base"} or target.startswith("on"):
                return False
        for name, value in element.attrib.items():
            key = name.rsplit("}", 1)[-1].lower()
            if (
                key.startswith("on")
                or name == "{http://www.w3.org/XML/1998/namespace}base"
            ):
                return False
            if key in {"href", "src"} and not _local_svg_reference(value):
                return False
            if not _valid_svg_style(value, css=key == "style"):
                return False
        if tag == "style" and not _valid_svg_style(
            "".join(element.itertext()), css=True
        ):
            return False
    return True


def read_plugin_icon(root: Path, name: str | None) -> tuple[bytes, str] | None:
    if not name:
        return None
    try:
        safe_path(name)
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            return None
        formats = {
            ".png": ("PNG", "image/png"),
            ".jpg": ("JPEG", "image/jpeg"),
            ".jpeg": ("JPEG", "image/jpeg"),
            ".webp": ("WEBP", "image/webp"),
            ".svg": ("SVG", "image/svg+xml"),
        }
        format_info = formats.get(path.suffix.lower())
        if not format_info:
            return None
        with path.open("rb") as icon:
            data = icon.read(256 * 1024 + 1)
        if len(data) > 256 * 1024:
            return None
        kind, media_type = format_info
        if not (_valid_svg(data) if kind == "SVG" else _valid_raster(data, kind)):
            return None
        return data, media_type
    except (OSError, ValueError):
        return None


def extract_package(
    content: bytes, target: Path, repository_archive: bool = False
) -> Manifest:
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
            wrapper: str | None = None
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
                if repository_archive:
                    root, _, relative = name.partition("/")
                    if wrapper is None:
                        wrapper = root
                    if root != wrapper or (not relative and not info.is_dir()):
                        raise PackageValidationError(
                            "Invalid GitHub repository archive layout"
                        )
                    name = relative
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
            manifest.resolve_detail(target)
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
