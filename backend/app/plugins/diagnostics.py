"""Opt-in bounded, in-memory diagnostics. Normal hosts retain no trace payloads."""

import inspect
import json
import re
import time
from collections import deque
from datetime import UTC, datetime
from functools import wraps

SENSITIVE = re.compile(
    r"authorization|cookie|password|secret|credential|api[-_]?key|access[-_]?token|refresh[-_]?token|id[-_]?token|client[-_]?secret",
    re.I,
)


class Diagnostics:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.entries = deque(maxlen=200)
        self.sequence = 0
        self.known_secrets: dict[str, set[str]] = {}

    def redact(self, value, plugin=None, depth=0):
        if depth > 24:
            return "[depth limit]"
        plugin_id = plugin.manifest.id if plugin else ""
        secrets = self.known_secrets.setdefault(plugin_id, set())
        if plugin:
            secrets.update(
                str(plugin.settings[s.key])
                for s in plugin.manifest.settings
                if s.secret and plugin.settings.get(s.key)
            )
        if isinstance(value, dict):
            return {
                str(key): "[redacted]"
                if SENSITIVE.search(str(key))
                else self.redact(item, plugin, depth + 1)
                for key, item in list(value.items())[:250]
            }
        if isinstance(value, (list, tuple)):
            return [self.redact(item, plugin, depth + 1) for item in value[:250]]
        if isinstance(value, str):
            for secret in sorted(secrets, key=len, reverse=True):
                if secret:
                    value = value.replace(secret, "[redacted]")
            value = re.sub(r"(?i)Bearer\s+[^\s\"',}]+", "Bearer [redacted]", value)
            if value.lstrip().startswith(("{", "[")) and len(value) < 64000:
                try:
                    return json.dumps(
                        self.redact(json.loads(value), plugin, depth + 1),
                        ensure_ascii=False,
                    )
                except ValueError:
                    pass
            return value[:24000] + ("…[truncated]" if len(value) > 24000 else "")
        if value is None or type(value) in {bool, int, float}:
            return value
        return "[" + type(value).__name__ + "]"

    def add(
        self,
        plugin,
        kind,
        method,
        request=None,
        result=None,
        error=None,
        duration=0,
        view_id=None,
    ):
        if not self.enabled:
            return
        self.sequence += 1
        payload = self.redact(
            {"request": request, "result": result, "error": error}, plugin
        )
        if len(json.dumps(payload, ensure_ascii=False)) > 64000:
            payload = {
                "request": "[payload truncated]",
                "result": "[payload truncated]",
                "error": payload["error"],
            }
        self.entries.append(
            {
                "sequence": self.sequence,
                "time": datetime.now(UTC).isoformat(),
                "pluginId": plugin.manifest.id,
                "viewId": view_id
                or (request.get("viewId") if isinstance(request, dict) else None),
                "kind": kind,
                "method": method,
                "status": "error" if error else "ok",
                "durationMs": round(duration * 1000, 2),
                **payload,
            }
        )

    async def run(self, plugin, kind, method, request, invoke):
        if not self.enabled:
            return await invoke()
        started = time.perf_counter()
        hidden = (
            method.startswith("secrets.") or request.get("namespace") == "secrets"
            if isinstance(request, dict)
            else method.startswith("secrets.")
        )
        try:
            result = await invoke()
        except BaseException as error:
            self.add(
                plugin,
                kind,
                method,
                "[redacted]" if hidden else request,
                error=type(error).__name__
                + (": [redacted]" if hidden else ": " + str(error)),
                duration=time.perf_counter() - started,
            )
            raise
        if hidden:

            def collect(value):
                if isinstance(value, str) and 1 <= len(value) <= 8192:
                    self.known_secrets.setdefault(plugin.manifest.id, set()).add(value)
                elif isinstance(value, dict):
                    for item in list(value.values())[:100]:
                        collect(item)
                elif isinstance(value, list):
                    for item in value[:100]:
                        collect(item)

            collect(result)
        self.add(
            plugin,
            kind,
            method,
            "[redacted]" if hidden else request,
            "[redacted]" if hidden else result,
            duration=time.perf_counter() - started,
        )
        return result

    def snapshot(self, plugin_id=None):
        return {
            "enabled": self.enabled,
            "cursor": self.sequence,
            "entries": [
                e
                for e in self.entries
                if plugin_id is None or e["pluginId"] == plugin_id
            ],
        }

    def clear(self, plugin_id=None):
        self.entries = deque(
            (
                e
                for e in self.entries
                if plugin_id is not None and e["pluginId"] != plugin_id
            ),
            maxlen=200,
        )


def traced(method):
    """Trace an async public service call without changing the returned value."""

    def decorate(function):
        signature = inspect.signature(function)

        @wraps(function)
        async def call(self, *args, **kwargs):
            context = getattr(self, "trace_context", None) or getattr(
                self, "context", None
            )
            host = context.host if context else getattr(self, "host", None)
            if not host or not host.diagnostics.enabled:
                return await function(self, *args, **kwargs)
            plugin = context.plugin if context else self.plugin
            params = dict(signature.bind(self, *args, **kwargs).arguments)
            params.pop("self", None)
            name = method
            if getattr(self, "secret", False):
                name = method.replace("storage.", "secrets.")
            return await host.diagnostics.run(
                plugin, "sdk", name, params, lambda: function(self, *args, **kwargs)
            )

        return call

    return decorate
