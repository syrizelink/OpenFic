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
from app.plugins.services import bounded_json

_active_host: Any = None


def active_host():
    return _active_host


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
    tools: dict[str, dict] = field(default_factory=dict)
    hooks: dict[str, list] = field(default_factory=dict)
    graphs: dict[str, Any] = field(default_factory=dict)
    disposables: list[Any] = field(default_factory=list)
    intervals: list[tuple[float, Any]] = field(default_factory=list)

    def register_command(self, name: str, handler: Handler) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,79}", name) or not callable(handler):
            raise ValueError("Invalid plugin command")
        if name in self.commands:
            raise ValueError(f"Duplicate command: {name}")
        self.commands[name] = handler

    def register_tool(
        self,
        name: str,
        description: str,
        schema: dict,
        handler: Handler,
        *,
        access_level="write",
    ):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name) or name in self.tools:
            raise ValueError("Invalid or duplicate tool name")
        if schema.get("type") != "object" or access_level not in {"write", "readonly"}:
            raise ValueError(
                "Tools require an object JSON schema and valid access level"
            )
        import jsonschema

        jsonschema.Draft202012Validator.check_schema(schema)

        def references(value):
            if isinstance(value, dict):
                if "$ref" in value and not value["$ref"].startswith("#"):
                    raise ValueError("Tool schemas cannot fetch external references")
                for child in value.values():
                    references(child)
            elif isinstance(value, list):
                for child in value:
                    references(child)

        references(schema)
        self.tools[name] = {
            "description": description,
            "schema": schema,
            "handler": handler,
            "access_level": access_level,
        }

    def register_hook(self, event: str, handler, *, priority=0):
        from app.plugins.runtime import EVENTS

        if event not in EVENTS:
            raise ValueError(f"Unsupported event: {event}")
        self.hooks.setdefault(event, []).append((priority, handler))

    def register_graph(self, name: str, factory):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", name) or name in self.graphs:
            raise ValueError("Invalid or duplicate graph provider")
        self.graphs[name] = factory

    def on_dispose(self, callback):
        self.disposables.append(callback)

    def register_interval(self, seconds: float, handler):
        if not 5 <= seconds <= 86400 or not callable(handler):
            raise ValueError("Intervals must be between 5 seconds and 24 hours")
        self.intervals.append((seconds, handler))


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
        self._events: list[dict] = []
        self._event_sequence = 0
        self.http_transport = None
        self.application = None
        self.oauth_flows: dict[str, dict] = {}

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
        def saved_settings(plugin):
            values = dict(plugin.settings)
            for setting in plugin.manifest.settings:
                if setting.secret and values.get(setting.key):
                    from app.plugins.services import PluginStorage

                    cipher = PluginStorage(self, plugin, secret=True)._cipher()
                    values[setting.key] = {
                        "encrypted": cipher.encrypt(
                            json.dumps(values[setting.key]).encode()
                        ).decode()
                    }
            return values

        self._write_json(
            self.root / ".registry.json",
            {
                key: {"enabled": plugin.enabled, "settings": saved_settings(plugin)}
                for key, plugin in self.plugins.items()
            },
        )

    async def start(self):
        global _active_host
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
                    settings_values = saved.get("settings", {})
                    for setting in manifest.settings:
                        value = settings_values.get(setting.key)
                        if (
                            setting.secret
                            and isinstance(value, dict)
                            and "encrypted" in value
                        ):
                            from app.plugins.services import PluginStorage

                            cipher = PluginStorage(self, None, secret=True)._cipher()
                            settings_values[setting.key] = json.loads(
                                cipher.decrypt(value["encrypted"].encode())
                            )
                    settings = manifest.validate_settings(settings_values)
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
            _active_host = self

    async def close(self):
        global _active_host
        async with self._lock:
            for plugin in self.plugins.values():
                await self._deactivate(plugin)
            self._started = False
            self.plugins.clear()
            if _active_host is self:
                _active_host = None

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
            "configuration": {
                s.key: ("" if s.secret else plugin.settings[s.key])
                for s in plugin.manifest.settings
            },
            "configured_secrets": [
                s.key
                for s in plugin.manifest.settings
                if s.secret and plugin.settings[s.key]
            ],
            "commands": sorted(plugin.registration.commands)
            if plugin.registration
            else [],
            "tools": [
                f"plugin_{plugin.manifest.id.replace('-', '_')}_{name}"
                for name in plugin.registration.tools
            ]
            if plugin.registration
            else [],
            "hooks": list(plugin.registration.hooks) if plugin.registration else [],
            "graphs": [
                f"{plugin.manifest.id}/{name}" for name in plugin.registration.graphs
            ]
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
            requirements = [
                (registration.tools, "agent.tools"),
                (registration.hooks, "agent.hooks"),
                (registration.graphs, "agent.graph"),
                (registration.intervals, "timers"),
                (registration.hooks.get("editor.change"), "editor.read"),
            ]
            for entries, capability in requirements:
                if entries and capability not in manifest.capabilities:
                    raise PermissionError(f"Plugin has not declared {capability}")
            for view in manifest.views:
                if view.renderer == "declarative" and (
                    view.render not in registration.commands
                    or view.action not in registration.commands
                ):
                    raise ValueError(
                        f"Declarative view {view.id} references an unregistered command"
                    )
            plugin.module_name = module_name if manifest.backend else None
            plugin.registration = registration
            for seconds, handler in registration.intervals:
                task = asyncio.create_task(self._run_interval(plugin, seconds, handler))

                async def dispose(task=task):
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                registration.on_dispose(dispose)
            plugin.error = None
            self._log(manifest.id, "enable", "Plugin activated")
        except BaseException:
            if plugin.registration is None:
                plugin.registration = registration
            await self._deactivate(plugin)
            sys.modules.pop(module_name, None)
            raise

    async def _run_interval(self, plugin, seconds, handler):
        from app.storage.database import create_session

        while True:
            await asyncio.sleep(seconds)
            async with self._lock:
                if not plugin.registration:
                    return
                try:
                    async with await create_session() as session:
                        async with asyncio.timeout(60):
                            await _await_result(
                                handler(self.context(plugin.manifest.id, session), {})
                            )
                        await session.commit()
                except Exception as error:
                    self._log(plugin.manifest.id, "timer", str(error), "error")

    async def _deactivate(self, plugin: Installed):
        self.oauth_flows = {
            k: v
            for k, v in self.oauth_flows.items()
            if v["plugin_id"] != plugin.manifest.id
        }
        self._view_tickets = {
            token: ticket
            for token, ticket in self._view_tickets.items()
            if ticket[0] != plugin.manifest.id
        }
        if plugin.registration:
            for callback in reversed(plugin.registration.disposables):
                try:
                    async with asyncio.timeout(5):
                        await _await_result(callback())
                except Exception as error:
                    self._log(plugin.manifest.id, "dispose", str(error), "error")
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
                if not (target / "plugin.json").exists():
                    raise PluginError("Package must contain plugin.json at the archive root")
                manifest = Manifest.model_validate_json(
                    (target / "plugin.json").read_bytes()
                )
                entries = [view.entry for view in manifest.views if view.entry]
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
                for setting in plugin.manifest.settings:
                    if setting.secret and settings.get(setting.key) == "":
                        settings[setting.key] = plugin.settings.get(
                            setting.key, setting.default
                        )
                plugin.settings = plugin.manifest.validate_settings(settings)
            except ValueError as error:
                raise PluginError(str(error)) from error
            self._persist()
            self._log(plugin_id, "configure", "Configuration updated")
            self.emit("ui.invalidate", {}, plugin_id)
            return self.describe(plugin)

    async def uninstall(self, plugin_id: str):
        async with self._lock:
            plugin = self.get(plugin_id)
            await self._deactivate(plugin)
            shutil.rmtree(self.root / plugin_id)
            shutil.rmtree(self.root / ".data" / plugin_id, ignore_errors=True)
            del self.plugins[plugin_id]
            self._persist()
            self._log(plugin_id, "uninstall", "Plugin removed")

    async def call(
        self,
        plugin_id: str,
        method: str,
        params: dict[str, Any],
        session: AsyncSession,
        *,
        runtime: dict | None = None,
    ):
        async with self._lock:
            plugin = self.get(plugin_id)
            if not plugin.enabled or plugin.registration is None:
                raise PluginError("Plugin is not active", 409)
            handler = plugin.registration.commands.get(method)
            if handler is None and not method.startswith("sdk."):
                raise PluginError("Plugin command not found", 404)
            context = self.context(plugin_id, session, runtime)
            try:
                async with asyncio.timeout(120):
                    if method.startswith("sdk."):
                        from app.plugins.runtime import sdk_call

                        result = await sdk_call(context, method[4:], params)
                    else:
                        assert handler is not None
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

    def context(self, plugin_id, session, runtime=None):
        plugin = self.get(plugin_id)
        private = dict(runtime or {})
        public = {
            key: value for key, value in private.items() if not key.startswith("_")
        }
        if isinstance(public.get("model_config"), dict):
            public["model_config"] = {
                key: value
                for key, value in public["model_config"].items()
                if key not in {"api_key", "custom_headers"}
            }
        return PluginContext(
            plugin_id,
            dict(plugin.settings),
            ProjectData(session, plugin.manifest.capabilities),
            self,
            public,
            private,
        )

    def emit(self, event: str, data: dict, plugin_id=None):
        self._event_sequence += 1
        self._events.append(
            {
                "sequence": self._event_sequence,
                "event": event,
                "data": bounded_json(data, 256_000),
                "pluginId": plugin_id,
            }
        )
        self._events = self._events[-500:]
        return self._event_sequence

    def events(self, after=0):
        return {
            "cursor": self._event_sequence,
            "events": [event for event in self._events if event["sequence"] > after],
        }

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
        if view.renderer != "iframe" or view.entry is None:
            raise PluginError("This view uses declarative rendering", 409)
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
