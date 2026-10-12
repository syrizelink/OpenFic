"""Single-instance plugin lifecycle, atomic package replacement and RPC registry."""

import asyncio
import importlib.util
import inspect
import io
import json
import re
import secrets
import shutil
import stat
import sys
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.plugins.manifest import (
    MAX_EXPANDED_BYTES,
    MAX_PACKAGE_BYTES,
    Manifest,
    safe_path,
)
from app.plugins.sdk import PluginContext, ProjectData

Handler = Callable[[PluginContext, dict[str, Any]], Awaitable[Any]]


class PluginError(HTTPException):
    def __init__(self, message: str, status: int = 400):
        super().__init__(status_code=status, detail=message)
        self.status = status

    def __str__(self):
        return str(self.detail)


@dataclass
class Registration:
    """A fresh registry per activation; disposal removes every command at once."""

    commands: dict[str, Handler] = field(default_factory=dict)

    def register_command(self, name: str, handler: Handler) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,79}", name) or not callable(handler):
            raise ValueError("Invalid plugin command")
        if name in self.commands:
            raise ValueError(f"Duplicate command: {name}")
        self.commands[name] = handler


@dataclass
class Installed:
    manifest: Manifest
    enabled: bool = False
    settings: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    registration: Registration | None = None
    module_name: str | None = None


async def _await_result(value):
    if inspect.isawaitable(value):
        return await value
    return value


class PluginHost:
    def __init__(self, root: Path):
        self.root = root
        self.plugins: dict[str, Installed] = {}
        self._lock = asyncio.Lock()
        self._started = False
        self._view_tickets: dict[str, tuple[str, float]] = {}

    def _log(self, plugin_id: str, action: str, message: str, level: str = "info"):
        entry = {
            "time": datetime.now(UTC).isoformat(),
            "action": action,
            "message": message,
            "level": level,
        }
        directory = self.root / ".logs"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{plugin_id}.json"
        try:
            existing = json.loads(path.read_text()) if path.exists() else []
        except (OSError, ValueError):
            existing = []
        self._write_json(path, [*existing, entry][-200:])

    @staticmethod
    def _write_json(path: Path, value: Any):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(path)

    def _persist(self):
        self._write_json(
            self.root / ".registry.json",
            {
                key: {"enabled": plugin.enabled, "settings": plugin.settings}
                for key, plugin in self.plugins.items()
            },
        )

    async def start(self):
        async with self._lock:
            if self._started:
                return
            self.root.mkdir(parents=True, exist_ok=True)
            # Recover a package swap interrupted between directory renames.
            for backup in self.root.glob(".backup-*"):
                target = self.root / backup.name.removeprefix(".backup-")
                if target.exists():
                    shutil.rmtree(backup)
                else:
                    backup.replace(target)
            for staging in self.root.glob(".install-*"):
                shutil.rmtree(staging)
            try:
                state = json.loads(
                    (self.root / ".registry.json").read_text(encoding="utf-8")
                )
                if not isinstance(state, dict):
                    state = {}
            except (OSError, ValueError):
                state = {}
            for directory in sorted(self.root.iterdir()):
                if (
                    directory.name.startswith(".")
                    or not directory.is_dir()
                    or directory.is_symlink()
                ):
                    continue
                try:
                    manifest = Manifest.model_validate_json(
                        (directory / "plugin.json").read_bytes()
                    )
                    if manifest.id != directory.name:
                        raise ValueError("Plugin directory identity mismatch")
                    saved = state.get(manifest.id, {})
                    settings = manifest.validate_settings(saved.get("settings", {}))
                    plugin = Installed(
                        manifest, bool(saved.get("enabled", False)), settings
                    )
                    self.plugins[manifest.id] = plugin
                    if plugin.enabled:
                        try:
                            await self._activate(plugin)
                        except Exception as error:
                            plugin.error = str(error)
                            self._log(manifest.id, "startup", str(error), "error")
                except Exception as error:
                    logger.warning(
                        "Unable to discover plugin {}: {}", directory.name, error
                    )
            self._started = True

    async def close(self):
        async with self._lock:
            for plugin in self.plugins.values():
                await self._deactivate(plugin)
            self._started = False
            self.plugins.clear()

    def get(self, plugin_id: str) -> Installed:
        plugin = self.plugins.get(plugin_id)
        if plugin is None:
            raise PluginError("Plugin not found", 404)
        return plugin

    def describe(self, plugin: Installed) -> dict[str, Any]:
        return {
            **plugin.manifest.model_dump(),
            "enabled": plugin.enabled,
            "status": "error"
            if plugin.error
            else "enabled"
            if plugin.registration
            else "disabled",
            "error": plugin.error,
            "configuration": plugin.settings,
            "commands": sorted(plugin.registration.commands)
            if plugin.registration
            else [],
        }

    async def _activate(self, plugin: Installed):
        registration = Registration()
        manifest = plugin.manifest
        module_name = (
            f"_openfic_plugin_{manifest.id.replace('-', '_')}_{uuid.uuid4().hex}"
        )
        try:
            if manifest.backend:
                entry = self.root / manifest.id / manifest.backend
                spec = importlib.util.spec_from_file_location(module_name, entry)
                if spec is None or spec.loader is None:
                    raise ValueError("Cannot load backend entry")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                plugin.module_name = module_name
                spec.loader.exec_module(module)
                register = getattr(module, "register", None)
                if not callable(register):
                    raise ValueError("Backend must export register(host)")
                async with asyncio.timeout(15):
                    await _await_result(register(registration))
            plugin.module_name = module_name if manifest.backend else None
            plugin.registration = registration
            plugin.error = None
            self._log(manifest.id, "enable", "Plugin activated")
        except BaseException:
            await self._deactivate(plugin)
            sys.modules.pop(module_name, None)
            raise

    async def _deactivate(self, plugin: Installed):
        self._view_tickets = {
            token: ticket
            for token, ticket in self._view_tickets.items()
            if ticket[0] != plugin.manifest.id
        }
        if plugin.module_name:
            module = sys.modules.get(plugin.module_name)
            deactivate = getattr(module, "deactivate", None)
            try:
                if callable(deactivate):
                    async with asyncio.timeout(5):
                        await _await_result(deactivate())
            except Exception as error:
                self._log(plugin.manifest.id, "disable", str(error), "error")
            finally:
                sys.modules.pop(plugin.module_name, None)
        plugin.module_name = None
        plugin.registration = None

    def _extract(self, content: bytes, target: Path) -> Manifest:
        if not content or len(content) > MAX_PACKAGE_BYTES:
            raise PluginError("Package must be between 1 byte and 20 MiB")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                files = [info for info in archive.infolist() if not info.is_dir()]
                if (
                    len(archive.infolist()) > 512
                    or sum(info.file_size for info in files) > MAX_EXPANDED_BYTES
                ):
                    raise PluginError("Package exceeds extraction limits")
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
                        raise PluginError(
                            "Duplicate, encrypted or symbolic-link archive entry"
                        )
                    seen.add(name.casefold())
                    if info.is_dir():
                        continue
                    destination = target / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(info))
                manifest = Manifest.model_validate_json(
                    (target / "plugin.json").read_bytes()
                )
                entries = [view.entry for view in manifest.views]
                if manifest.backend:
                    entries.append(manifest.backend)
                if any(not (target / entry).is_file() for entry in entries):
                    raise PluginError("Manifest references a missing entry file")
                return manifest
        except PluginError:
            raise
        except (ValueError, OSError, zipfile.BadZipFile, RuntimeError) as error:
            raise PluginError(f"Invalid plugin package: {error}") from error

    async def install(
        self, content: bytes, update_id: str | None = None
    ) -> dict[str, Any]:
        async with self._lock:
            stage = Path(tempfile.mkdtemp(prefix=".install-", dir=self.root))
            try:
                manifest = self._extract(content, stage)
                old = self.plugins.get(manifest.id)
                if update_id is not None and (manifest.id != update_id or old is None):
                    raise PluginError(
                        "Update package identity does not match installed plugin"
                    )
                if old is not None and update_id is None:
                    raise PluginError("Plugin already installed; use Update", 409)
                if old and tuple(map(int, manifest.version.split("."))) <= tuple(
                    map(int, old.manifest.version.split("."))
                ):
                    raise PluginError(
                        "Update version must be newer than installed version", 409
                    )
                settings = manifest.validate_settings(
                    {
                        item.key: old.settings[item.key]
                        for item in manifest.settings
                        if old and item.key in old.settings
                    }
                )
                plugin = Installed(manifest, bool(old and old.enabled), settings)
                destination = self.root / manifest.id
                backup = self.root / f".backup-{manifest.id}"
                old_moved = False
                stage_installed = False
                try:
                    if old:
                        await self._deactivate(old)
                        destination.replace(backup)
                        old_moved = True
                    stage.replace(destination)
                    stage_installed = True
                    self.plugins[manifest.id] = plugin
                    if plugin.enabled:
                        await self._activate(plugin)
                    self._persist()
                except BaseException as error:
                    await self._deactivate(plugin)
                    if stage_installed:
                        shutil.rmtree(destination)
                    if old:
                        if old_moved:
                            backup.replace(destination)
                        self.plugins[manifest.id] = old
                        if old.enabled and old.registration is None:
                            await self._activate(old)
                    else:
                        self.plugins.pop(manifest.id, None)
                    self._persist()
                    self._log(manifest.id, "update", f"Rolled back: {error}", "error")
                    if not isinstance(error, Exception):
                        raise
                    raise PluginError(
                        f"Installation failed; previous state restored: {error}"
                    ) from error
                if backup.exists():
                    shutil.rmtree(backup)
                self._log(
                    manifest.id,
                    "update" if old else "install",
                    f"Installed {manifest.version}",
                )
                return self.describe(plugin)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)

    async def set_enabled(self, plugin_id: str, enabled: bool) -> dict[str, Any]:
        async with self._lock:
            plugin = self.get(plugin_id)
            await self._deactivate(plugin)
            plugin.error = None
            plugin.enabled = enabled
            try:
                if enabled:
                    await self._activate(plugin)
            except Exception as error:
                plugin.error = str(error)
                plugin.enabled = False
                self._log(plugin_id, "enable", str(error), "error")
                raise PluginError(f"Plugin activation failed: {error}") from error
            finally:
                self._persist()
            if not enabled:
                self._log(
                    plugin_id, "disable", "Plugin disabled; registrations disposed"
                )
            return self.describe(plugin)

    async def configure(
        self, plugin_id: str, settings: dict[str, Any]
    ) -> dict[str, Any]:
        async with self._lock:
            plugin = self.get(plugin_id)
            try:
                plugin.settings = plugin.manifest.validate_settings(settings)
            except ValueError as error:
                raise PluginError(str(error)) from error
            self._persist()
            self._log(plugin_id, "configure", "Configuration updated")
            return self.describe(plugin)

    async def uninstall(self, plugin_id: str):
        async with self._lock:
            plugin = self.get(plugin_id)
            await self._deactivate(plugin)
            shutil.rmtree(self.root / plugin_id)
            del self.plugins[plugin_id]
            self._persist()
            self._log(plugin_id, "uninstall", "Plugin removed")

    async def call(
        self, plugin_id: str, method: str, params: dict[str, Any], session: AsyncSession
    ):
        async with self._lock:
            plugin = self.get(plugin_id)
            if not plugin.enabled or plugin.registration is None:
                raise PluginError("Plugin is not active", 409)
            handler = plugin.registration.commands.get(method)
            if handler is None:
                raise PluginError("Plugin command not found", 404)
            context = PluginContext(
                plugin_id,
                dict(plugin.settings),
                ProjectData(session, plugin.manifest.capabilities),
            )
            try:
                async with asyncio.timeout(15):
                    result = await _await_result(handler(context, params))
                encoded = json.dumps(result, allow_nan=False)
                if len(encoded.encode()) > 4 * 1024 * 1024:
                    raise ValueError("Plugin response exceeds 4 MiB")
                return json.loads(encoded)
            except Exception as error:
                self._log(plugin_id, "command", f"{method}: {error}", "error")
                raise PluginError(
                    str(error) or "Plugin command timed out", 422
                ) from error

    def logs(self, plugin_id: str) -> list[dict[str, Any]]:
        self.get(plugin_id)
        path = self.root / ".logs" / f"{plugin_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def asset(self, plugin_id: str, filename: str) -> Path:
        plugin = self.get(plugin_id)
        if plugin.registration is None:
            raise PluginError("Plugin is not active", 409)
        try:
            safe_path(filename)
        except ValueError as error:
            raise PluginError("Invalid asset path", 404) from error
        base = (self.root / plugin_id / "frontend").resolve()
        path = (base / filename).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise PluginError("Plugin asset not found", 404)
        return path

    def open_view(self, plugin_id: str, view_id: str) -> str:
        plugin = self.get(plugin_id)
        view = next(
            (view for view in plugin.manifest.views if view.id == view_id), None
        )
        if plugin.registration is None or view is None:
            raise PluginError("Plugin view is unavailable", 404)
        now = time.monotonic()
        self._view_tickets = {
            token: ticket
            for token, ticket in self._view_tickets.items()
            if ticket[1] > now
        }
        if len(self._view_tickets) >= 4096:
            raise PluginError("Too many active plugin views", 429)
        token = secrets.token_urlsafe(32)
        self._view_tickets[token] = (plugin_id, now + 900)
        return f"/plugin-assets/{token}/{plugin_id}/assets/{view.entry.removeprefix('frontend/')}"

    def ticket_plugin(self, token: str) -> str:
        ticket = self._view_tickets.get(token)
        if ticket is None or ticket[1] <= time.monotonic():
            self._view_tickets.pop(token, None)
            raise PluginError("Plugin view ticket expired or invalid", 404)
        plugin_id = ticket[0]
        if self.get(plugin_id).registration is None:
            raise PluginError("Plugin is not active", 409)
        return plugin_id
