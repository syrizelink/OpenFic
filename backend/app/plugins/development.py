"""Explicit local development session. Never watch arbitrary paths from HTTP."""

import asyncio
import hashlib
from contextlib import suppress
from pathlib import Path

from app.plugins.checker import check_plugin
from app.plugins.packages import build_package, source_files


class DevelopmentSession:
    def __init__(self, host, source: Path):
        self.host, self.source = host, source.resolve()
        self.plugin_id = None
        self.revision = 0
        self.status = "starting"
        self.report = {"diagnostics": [], "checks": []}
        self._digest = None
        self._stamp = None
        self._task = None
        self._reload_lock = asyncio.Lock()

    def describe(self):
        return {
            "enabled": True,
            "inspector": self.host.diagnostics.enabled,
            "pluginId": self.plugin_id,
            "source": str(self.source),
            "revision": self.revision,
            "status": self.status,
            **self.report,
        }

    async def start(self):
        self.host.development = self
        self.host.diagnostics.enabled = True
        try:
            self._stamp = await asyncio.to_thread(self._fingerprint)
        except (ValueError, OSError):
            self._stamp = None
        await self.reload()
        self._task = asyncio.create_task(self._watch())

    async def close(self):
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self.host.development = None

    async def reload(self):
        async with self._reload_lock:
            try:
                self.report = await asyncio.to_thread(check_plugin, self.source)
                if not self.report["ok"]:
                    self.status = "error"
                    return self.describe()
                plugin_id = self.report["pluginId"]
                if self.plugin_id and plugin_id != self.plugin_id:
                    raise ValueError(
                        "Development plugin identity changed; restart the development server"
                    )
                content = await asyncio.to_thread(build_package, self.source)
                digest = hashlib.sha256(content).hexdigest()
                if digest == self._digest:
                    self.status = "ready"
                    return self.describe()
                self.plugin_id = plugin_id
                installed = self.host.plugins.get(plugin_id)
                await self.host.install(
                    content, update_id=plugin_id if installed else None
                )
                if not installed:
                    await self.host.set_enabled(plugin_id, True)
                self._digest = digest
                self.revision += 1
                self.status = "ready"
                self.host.emit("ui.invalidate", {}, plugin_id)
            except Exception as error:
                plugin = self.host.plugins.get(self.plugin_id)
                self.report = {
                    "diagnostics": [
                        {
                            "code": "development.reload",
                            "severity": "error",
                            "file": "plugin.json",
                            "line": None,
                            "message": self.host.diagnostics.redact(str(error), plugin),
                        }
                    ],
                    "checks": [],
                }
                self.status = "error"
            return self.describe()

    def _fingerprint(self):
        return tuple(
            (
                str(path.relative_to(self.source)),
                path.stat().st_mtime_ns,
                path.stat().st_size,
            )
            for path in source_files(self.source)
        )

    async def _watch(self):
        while True:
            await asyncio.sleep(0.75)
            try:
                stamp = await asyncio.to_thread(self._fingerprint)
                if stamp != self._stamp:
                    self._stamp = stamp
                    await asyncio.sleep(0.2)
                    await self.reload()
            except (ValueError, OSError):
                self.status = "error"
                self.report = {
                    "diagnostics": [
                        {
                            "code": "development.source",
                            "severity": "error",
                            "file": "plugin.json",
                            "message": "Source directory could not be read safely",
                        }
                    ],
                    "checks": [],
                }
