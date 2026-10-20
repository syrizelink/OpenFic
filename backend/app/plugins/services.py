"""Plugin-scoped persistence, secrets, files, HTTP and model services."""

import base64
import json
import os
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import Fernet

from app.plugins.manifest import safe_path


def bounded_json(value, maximum=4 * 1024 * 1024):
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > maximum:
        raise ValueError("Plugin data exceeds size limit")
    return json.loads(encoded)


class PluginAssets:
    """Read immutable frontend resources from this plugin's own package."""

    def __init__(self, host, plugin):
        self.host, self.plugin = host, plugin

    async def read(self, name: str):
        import mimetypes

        if "ui" not in self.plugin.manifest.capabilities:
            raise PermissionError("Plugin has not declared ui")
        base = (self.host.root / self.plugin.manifest.id / "frontend").resolve()
        path = (base / safe_path(name)).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise ValueError(
                "Asset must be a file inside this plugin's frontend directory"
            )
        if path.stat().st_size > 3 * 1024 * 1024 - 4096:
            raise ValueError("Asset exceeds bridge transfer limit")
        return {
            "name": name,
            "mime": mimetypes.guess_type(name)[0] or "application/octet-stream",
            "base64": base64.b64encode(path.read_bytes()).decode(),
        }


class PluginStorage:
    def __init__(self, host, plugin, *, secret=False):
        self.host, self.plugin, self.secret = host, plugin, secret

    def _path(self):
        capability = "secrets" if self.secret else "storage"
        if capability not in self.plugin.manifest.capabilities:
            raise PermissionError(f"Plugin has not declared {capability}")
        directory = self.host.root / ".data" / self.plugin.manifest.id
        directory.mkdir(parents=True, exist_ok=True)
        return directory / ("secrets.json" if self.secret else "storage.json")

    def _cipher(self):
        path = self.host.root / ".secret-key"
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(Fernet.generate_key())
        return Fernet(path.read_bytes())

    def _load(self):
        path = self._path()
        return json.loads(path.read_text()) if path.exists() else {}

    async def get(self, key: str, default=None):
        value = self._load().get(key)
        if value is None:
            return default
        return (
            json.loads(self._cipher().decrypt(value.encode())) if self.secret else value
        )

    async def set(self, key: str, value):
        if not isinstance(key, str) or not key or len(key) > 250:
            raise ValueError("Invalid storage key")
        value = bounded_json(value)
        values = self._load()
        values[key] = (
            self._cipher().encrypt(json.dumps(value).encode()).decode()
            if self.secret
            else value
        )
        bounded_json(values, 8 * 1024 * 1024)
        self.host._write_json(self._path(), values)
        return value

    async def delete(self, key: str):
        values = self._load()
        found = key in values
        values.pop(key, None)
        self.host._write_json(self._path(), values)
        return found

    async def keys(self, prefix=""):
        return sorted(key for key in self._load() if key.startswith(prefix))


class PluginFiles:
    def __init__(self, host, plugin):
        self.host, self.plugin = host, plugin

    def path(self, name: str):
        if "files" not in self.plugin.manifest.capabilities:
            raise PermissionError("Plugin has not declared files")
        base = (self.host.root / ".data" / self.plugin.manifest.id / "files").resolve()
        target = (base / safe_path(name)).resolve()
        if not target.is_relative_to(base):
            raise ValueError("File is outside plugin data directory")
        return target

    async def read(self, name: str):
        path = self.path(name)
        if path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("File exceeds 4 MiB")
        return path.read_text(encoding="utf-8")

    async def write(self, name: str, text: str):
        if len(text.encode()) > 4 * 1024 * 1024:
            raise ValueError("File exceeds 4 MiB")
        path = self.path(name)
        base = self.path(".quota").parent
        total = (
            sum(p.stat().st_size for p in base.rglob("*") if p.is_file())
            if base.exists()
            else 0
        )
        if total + len(text.encode()) > 40 * 1024 * 1024:
            raise ValueError("Plugin files exceed 40 MiB quota")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)

    async def delete(self, name: str):
        self.path(name).unlink(missing_ok=True)

    async def list(self, name=""):
        path = self.path(name) if name else self.path(".listing").parent
        return sorted(p.name for p in path.iterdir()) if path.exists() else []


class PluginHTTP:
    def __init__(self, plugin, transport=None):
        self.plugin, self.transport = plugin, transport

    async def request(
        self, method: str, url: str, *, headers=None, json=None, body=None, form=None
    ):
        if "network" not in self.plugin.manifest.capabilities:
            raise PermissionError("Plugin has not declared network")
        parts = urlsplit(url)
        if parts.scheme not in {"https", "http"} or parts.username or parts.password:
            raise ValueError("Invalid HTTP URL")
        if parts.hostname not in self.plugin.manifest.network_hosts:
            raise PermissionError(f"Network host not declared: {parts.hostname}")
        if parts.scheme != "https" and parts.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise PermissionError(
                "HTTPS is required except explicit loopback development hosts"
            )
        async with httpx.AsyncClient(
            timeout=25, follow_redirects=False, transport=self.transport
        ) as client:
            async with client.stream(
                method.upper(), url, headers=headers, json=json, content=body, data=form
            ) as response:
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 8 * 1024 * 1024:
                        raise ValueError("Network response exceeds 8 MiB")
                text = content.decode("utf-8", errors="replace")
                try:
                    parsed = __import__("json").loads(text)
                except ValueError:
                    parsed = None
                return {
                    "status": response.status_code,
                    "ok": response.is_success,
                    "headers": dict(response.headers),
                    "text": text,
                    "json": parsed,
                    "base64": base64.b64encode(content).decode(),
                }


class PluginModels:
    def __init__(self, context):
        self.context = context

    async def create(self, model_id=None, **options):
        self.context.require("agent.models")
        from app.api.routers.agent_runtime import _resolve_model_config
        from app.agent_runtime.model_config import to_client_model_config
        from app.models.clients.model_factory import ModelConfig, create_chat_model

        config = self.context._private_runtime.get("model_config")
        if model_id:
            config = await _resolve_model_config(self.context.data._session, model_id)
        if not isinstance(config, dict):
            raise ValueError("Choose a model or invoke from an active Agent run")
        safe_options = {
            k: v
            for k, v in options.items()
            if k in {"temperature", "max_tokens", "top_p"}
        }
        return create_chat_model(
            ModelConfig(**{**to_client_model_config(config), **safe_options})
        )

    async def complete(self, messages: list[dict], model_id=None, **options):
        from langchain_core.messages import convert_to_messages

        model = await self.create(model_id, **options)
        response = await model.ainvoke(convert_to_messages(messages))
        return {
            "role": "assistant",
            "content": response.content,
            "tool_calls": getattr(response, "tool_calls", []),
        }

    async def invoke(self, model, messages):
        self.context.require("agent.models")
        from app.agent_runtime.graph.react_agent import _invoke_model
        from app.agent_runtime.graph.llm_invoke import (
            invoke_model_with_retry,
            load_llm_invoke_settings,
        )

        return await invoke_model_with_retry(
            model,
            messages,
            invoke=_invoke_model,
            settings=load_llm_invoke_settings(),
            session_id=self.context.runtime.get("session_id"),
            node="plugin:" + self.context.plugin_id,
        )
