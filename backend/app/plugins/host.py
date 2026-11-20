"""Single-instance plugin lifecycle, atomic package replacement and RPC registry."""

import asyncio
import importlib.util
import inspect
import os
import json
import re
import secrets
import shutil
import sys
import tempfile
import time
import uuid
from collections import deque
from collections.abc import Iterator
from contextlib import suppress
from urllib.parse import quote
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from starlette.concurrency import run_in_threadpool
from fastapi import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.plugins.manifest import (
    Manifest,
    safe_path,
)
from app.plugins.sdk import PluginContext, ProjectData
from app.plugins.services import bounded_json
from app.socket.handlers import PLUGIN_LOGS_EVENT, PLUGIN_LOGS_ROOM

_active_host: Any = None


def active_host():
    return _active_host


Handler = Callable[[PluginContext, dict[str, Any]], Awaitable[Any]]
InstallStage = Literal["downloading", "validating", "installing", "complete"]
InstallProgress = Callable[[InstallStage, int], Awaitable[None]]


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
    reload_revision: int = 0


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
        self._notifications: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(
            maxsize=500
        )
        self._notification_task: asyncio.Task[None] | None = None
        self.http_transport = None
        self.application = None
        self.oauth_flows: dict[str, dict] = {}
        from app.plugins.diagnostics import Diagnostics

        self.diagnostics = Diagnostics(os.getenv("OPENFIC_PLUGIN_DEVTOOLS") == "1")
        self.development = None

    def _log(
        self, plugin_id: str, action: str, message: str, level: str = "info"
    ) -> None:
        entry = {
            "time": datetime.now(UTC).isoformat(),
            "action": action,
            "message": message,
            "level": level,
        }
        directory = self.root / ".logs"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / f"{plugin_id}.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._notify(PLUGIN_LOGS_EVENT, {"pluginId": plugin_id})

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
                key: {
                    "enabled": plugin.enabled,
                    "settings": saved_settings(plugin),
                    "order": order,
                }
                for order, (key, plugin) in enumerate(self.plugins.items())
            },
        )
        self._notify("plugins:changed", {})

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
            positions = {
                key: saved["order"]
                for key, saved in state.items()
                if isinstance(saved, dict)
                and type(saved.get("order")) is int
                and saved["order"] >= 0
            }
            for directory in sorted(
                self.root.iterdir(),
                key=lambda path: (positions.get(path.name, len(state)), path.name),
            ):
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
                    manifest.resolve_detail(directory)
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
            self._notification_task = asyncio.create_task(
                self._send_notifications(), name="plugin-notifications"
            )
            _active_host = self

    async def close(self):
        global _active_host
        async with self._lock:
            self._started = False
            if self._notification_task:
                self._notification_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._notification_task
                self._notification_task = None
            while not self._notifications.empty():
                self._notifications.get_nowait()
                self._notifications.task_done()
            for plugin in self.plugins.values():
                await self._deactivate(plugin)
            self.plugins.clear()
            if _active_host is self:
                _active_host = None

    def get(self, plugin_id: str) -> Installed:
        plugin = self.plugins.get(plugin_id)
        if plugin is None:
            raise PluginError("Plugin not found", 404)
        return plugin

    def detail_file(self, plugin_id: str, name: str | None = None) -> Path:
        plugin = self.get(plugin_id)
        if not plugin.manifest.detail:
            raise PluginError("Plugin detail not found", 404)
        if name is None:
            name = plugin.manifest.detail
        elif Path(name).suffix.lower() not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".avif",
            ".svg",
        }:
            raise PluginError("Plugin detail image not found", 404)
        try:
            safe_path(name)
            root = (self.root / plugin_id).resolve()
            path = (root / name).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("File is outside the plugin package")
            return path
        except ValueError as error:
            raise PluginError("Plugin detail file not found", 404) from error

    def icon_data(
        self, plugin_id: str, *, view_id: str | None = None
    ) -> tuple[bytes, str]:
        from app.plugins.packages import read_plugin_icon

        manifest = self.get(plugin_id).manifest
        root = self.root / plugin_id
        if view_id is not None:
            view = next(
                (
                    view
                    for view in manifest.views
                    if view.id == view_id and view.slot in {"sidebar.extensions", "settings"}
                ),
                None,
            )
            if view is None:
                raise PluginError("Plugin icon not found", 404)
            if result := read_plugin_icon(root, view.icon):
                return result
            if view.slot == "settings":
                raise PluginError("Plugin icon not found", 404)
        result = read_plugin_icon(root, manifest.icon)
        if result is None:
            raise PluginError("Plugin icon not found", 404)
        return result

    def describe(self, plugin: Installed) -> dict[str, Any]:
        return {
            **plugin.manifest.model_dump(),
            "reload_revision": plugin.reload_revision,
            "development_revision": self.development.revision
            if self.development and self.development.plugin_id == plugin.manifest.id
            else 0,
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
                if s.secret
                and plugin.settings[s.key] is not None
                and (
                    not isinstance(plugin.settings[s.key], str)
                    or plugin.settings[s.key].strip()
                )
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
            if manifest.entry:
                entry = self.root / manifest.id / manifest.entry
                spec = importlib.util.spec_from_file_location(
                    module_name, entry, submodule_search_locations=[str(entry.parent)]
                )
                if spec is None or spec.loader is None:
                    raise ValueError("Cannot load plugin entry")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                plugin.module_name = module_name
                spec.loader.exec_module(module)
                register = getattr(module, "register", None)
                if not callable(register):
                    raise ValueError("Plugin entry must export register(host)")
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
                if view.status and view.status not in registration.commands:
                    raise ValueError(f"Statusbar view {view.id} references an unregistered command")
                if view.renderer == "declarative" and view.presentation != "none" and (
                    (view.render is not None and view.render not in registration.commands)
                    or view.action not in registration.commands
                ):
                    raise ValueError(
                        f"Declarative view {view.id} references an unregistered command"
                    )
            plugin.module_name = module_name if manifest.entry else None
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
                for name in list(sys.modules):
                    if name == plugin.module_name or name.startswith(
                        plugin.module_name + "."
                    ):
                        sys.modules.pop(name, None)
        plugin.module_name = None
        plugin.registration = None

    def _extract(
        self, content: bytes, target: Path, repository_archive: bool
    ) -> Manifest:
        from app.plugins.packages import extract_package, PackageValidationError

        try:
            return extract_package(content, target, repository_archive)
        except PackageValidationError as error:
            raise PluginError(str(error)) from error

    async def install(
        self,
        content: bytes,
        update_id: str | None = None,
        *,
        repository_archive: bool = False,
        progress: InstallProgress | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            stage = Path(tempfile.mkdtemp(prefix=".install-", dir=self.root))
            try:
                if progress:
                    await progress("validating", 55)
                manifest = await run_in_threadpool(
                    self._extract, content, stage, repository_archive
                )
                old = self.plugins.get(manifest.id)
                if update_id is not None and (manifest.id != update_id or old is None):
                    raise PluginError(
                        "Update package identity does not match installed plugin"
                    )
                if old is not None and update_id is None:
                    raise PluginError("Plugin already installed; use Update", 409)
                if (
                    old
                    and not (
                        self.development and self.development.plugin_id == manifest.id
                    )
                    and tuple(map(int, manifest.version.split(".")))
                    <= tuple(map(int, old.manifest.version.split(".")))
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
                if progress:
                    await progress("installing", 85)
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
                if progress:
                    await progress("complete", 100)
                return self.describe(plugin)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)

    async def set_order(self, plugin_ids: list[str]) -> list[str]:
        async with self._lock:
            if len(plugin_ids) != len(self.plugins) or set(plugin_ids) != set(
                self.plugins
            ):
                raise ValueError(
                    "Order must contain every installed plugin exactly once"
                )
            previous = self.plugins
            self.plugins = {plugin_id: previous[plugin_id] for plugin_id in plugin_ids}
            try:
                self._persist()
            except BaseException:
                self.plugins = previous
                raise
            return list(self.plugins)

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

    async def reload(self, plugin_id: str) -> None:
        async with self._lock:
            previous = self.get(plugin_id)
            directory = self.root / plugin_id
            try:
                manifest_file = directory / "plugin.json"
                if directory.is_symlink() or manifest_file.is_symlink():
                    raise ValueError("Invalid installed plugin directory or manifest")
                manifest = Manifest.model_validate_json(
                    await run_in_threadpool(manifest_file.read_bytes)
                )
                if manifest.id != plugin_id:
                    raise ValueError("Plugin directory identity mismatch")
                manifest.resolve_detail(directory)
                entries = [manifest.entry, *(view.entry for view in manifest.views)]
                root = directory.resolve()
                for name in entries:
                    if name and (
                        not (path := (directory / name).resolve()).is_relative_to(root)
                        or not path.is_file()
                    ):
                        raise ValueError("Manifest references an invalid entry file")
                settings = manifest.validate_settings(
                    {
                        item.key: previous.settings[item.key]
                        for item in manifest.settings
                        if item.key in previous.settings
                    }
                )
            except (ValueError, OSError, RuntimeError) as error:
                raise PluginError(
                    "Cannot reload plugin: invalid manifest, files or settings"
                ) from error

            plugin = Installed(
                manifest,
                previous.enabled,
                settings,
                reload_revision=previous.reload_revision + 1,
            )
            await self._deactivate(previous)
            self.plugins[plugin_id] = plugin
            try:
                if plugin.enabled:
                    await self._activate(plugin)
            except Exception as error:
                plugin.error = self.diagnostics.redact(str(error), plugin)
                self._log(plugin_id, "reload", plugin.error, "error")
                raise PluginError(
                    f"Plugin activation failed: {plugin.error}"
                ) from error
            finally:
                self._persist()
            self._log(plugin_id, "reload", "Plugin reloaded")

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
                validated = plugin.manifest.validate_settings(settings)
                for setting in plugin.manifest.settings:
                    value = validated[setting.key]
                    if (
                        setting.required
                        and setting.type != "select"
                        and (
                            value is None
                            or (isinstance(value, str) and not value.strip())
                        )
                    ):
                        raise ValueError(f"Required setting is empty: {setting.key}")
                plugin.settings = validated
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
                        result = await self.diagnostics.run(
                            plugin,
                            "command",
                            method,
                            params,
                            lambda: _await_result(handler(context, params)),
                        )
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

    def _notify(self, event: str, data: dict[str, Any]) -> None:
        if not self._started:
            return
        if self._notifications.full():
            while not self._notifications.empty():
                self._notifications.get_nowait()
                self._notifications.task_done()
            self._notifications.put_nowait(("plugins:resync", {}))
        self._notifications.put_nowait((event, data))

    async def _send_notifications(self) -> None:
        from app.socket import emitter

        while True:
            event, data = await self._notifications.get()
            try:
                if event == PLUGIN_LOGS_EVENT:
                    await emitter.emit(event, data, room=PLUGIN_LOGS_ROOM)
                else:
                    await emitter.emit(event, data)
            except Exception:
                logger.warning("Unable to push plugin notification: {}", event)
            finally:
                self._notifications.task_done()

    def emit(self, event: str, data: dict, plugin_id: str | None = None) -> None:
        self._notify(
            "plugins:event",
            {
                "event": event,
                "data": bounded_json(data, 256_000),
                "pluginId": plugin_id,
            },
        )

    def iter_logs(self, plugin_id: str) -> Iterator[dict[str, str]]:
        self.get(plugin_id)
        directory = self.root / ".logs"
        with suppress(FileNotFoundError):
            yield from json.loads(
                (directory / f"{plugin_id}.json").read_text(encoding="utf-8")
            )
        with suppress(FileNotFoundError):
            with (directory / f"{plugin_id}.jsonl").open(encoding="utf-8") as file:
                for line in file:
                    if line.endswith("\n"):
                        yield json.loads(line)

    def logs(
        self, plugin_id: str, minutes: int | None = None, limit: int | None = None
    ) -> list[dict[str, str]]:
        entries = self.iter_logs(plugin_id)
        if minutes is not None:
            cutoff = (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat(
                timespec="microseconds"
            )
            entries = (entry for entry in entries if entry["time"] >= cutoff)
        return (
            list(deque(entries, maxlen=limit)) if limit is not None else list(entries)
        )

    def clear_logs(self, plugin_id: str) -> None:
        self.get(plugin_id)
        for suffix in ("json", "jsonl"):
            (self.root / ".logs" / f"{plugin_id}.{suffix}").unlink(missing_ok=True)
        self._notify(PLUGIN_LOGS_EVENT, {"pluginId": plugin_id})

    def asset(self, plugin_id: str, filename: str) -> Path:
        plugin = self.get(plugin_id)
        if plugin.registration is None:
            raise PluginError("Plugin is not active", 409)
        try:
            safe_path(filename)
        except ValueError as error:
            raise PluginError("Invalid asset path", 404) from error
        try:
            return plugin.manifest.resource_path(self.root / plugin_id, filename)
        except ValueError as error:
            raise PluginError("Plugin asset not found", 404) from error

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
        name = plugin.manifest.resource_url_name(view.entry)
        return f"/plugin-assets/{token}/{plugin_id}/assets/{quote(name, safe='/')}"

    def ticket_plugin(self, token: str) -> str:
        ticket = self._view_tickets.get(token)
        if ticket is None or ticket[1] <= time.monotonic():
            self._view_tickets.pop(token, None)
            raise PluginError("Plugin view ticket expired or invalid", 404)
        plugin_id = ticket[0]
        if self.get(plugin_id).registration is None:
            raise PluginError("Plugin is not active", 409)
        return plugin_id
