"""Instance-owned tunnel processes. Credentials are never persisted or logged."""

import asyncio
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator

Provider = Literal["cloudflare", "ngrok"]
STARTUP_TIMEOUT = 60


class TunnelStart(BaseModel):
    provider: Provider = "cloudflare"
    mode: Literal["quick", "managed-remote"] = "quick"
    token: SecretStr | None = None
    hostname: str | None = Field(default=None, max_length=253)

    @model_validator(mode="after")
    def validate_mode(self) -> "TunnelStart":
        if self.mode == "managed-remote":
            if self.provider != "cloudflare":
                raise ValueError("Managed tunnels require Cloudflare")
            if not self.token or not self.token.get_secret_value().strip():
                raise ValueError("Cloudflare tunnel token is required")
            if not self.hostname or not re.fullmatch(
                r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}",
                self.hostname,
            ):
                raise ValueError(
                    "A public hostname without a scheme or path is required"
                )
        return self


def executable(provider: Provider) -> str | None:
    name = "cloudflared" if provider == "cloudflare" else "ngrok"
    search_path = os.pathsep.join(
        [os.environ.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin"]
    )
    return shutil.which(name, path=search_path)


def public_url(provider: Provider, line: str) -> str | None:
    if provider == "cloudflare":
        match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com\b", line)
        return match.group(0) if match else None
    try:
        record = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(record, dict) or record.get("msg") != "started tunnel":
        return None
    url = record.get("url")
    return (
        url
        if isinstance(url, str) and re.fullmatch(r"https://[a-zA-Z0-9.-]+", url)
        else None
    )


async def terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()


class TunnelManager:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.process: asyncio.subprocess.Process | None = None
        self.monitor: asyncio.Task[None] | None = None
        self.provider: Provider | None = None
        self.mode: str | None = None
        self.status = "stopped"
        self.url: str | None = None
        self.error: str | None = None
        self.config_dir: tempfile.TemporaryDirectory[str] | None = None

    def snapshot(self) -> dict:
        return {
            "provider": self.provider,
            "mode": self.mode,
            "status": self.status,
            "url": self.url,
            "error": self.error,
            "providers": {
                name: bool(executable(name)) for name in ("cloudflare", "ngrok")
            },
        }

    async def start(self, payload: TunnelStart, port: int) -> dict:
        async with self.lock:
            if self.status in {"starting", "running"}:
                raise ValueError("Stop the active tunnel before starting another")
            binary = executable(payload.provider)
            if not binary:
                raise ValueError(
                    "Install cloudflared or ngrok on the OpenFic server first"
                )
            await self._stop()
            origin = f"http://127.0.0.1:{port}"
            env = os.environ.copy()
            if payload.provider == "ngrok":
                args = ["http", origin, "--log", "stdout", "--log-format", "json"]
            elif payload.mode == "managed-remote":
                args = ["tunnel", "--no-autoupdate", "run"]
                assert payload.token is not None
                env["TUNNEL_TOKEN"] = payload.token.get_secret_value().strip()
            else:
                # Isolate quick mode from any existing named-tunnel config.
                self.config_dir = tempfile.TemporaryDirectory(prefix="openfic-tunnel-")
                config_path = Path(self.config_dir.name) / "config.yml"
                config_path.write_text("{}\n", encoding="utf-8")
                args = [
                    "tunnel",
                    "--config",
                    str(config_path),
                    "--no-autoupdate",
                    "--url",
                    origin,
                ]
            self.provider, self.mode = payload.provider, payload.mode
            self.status, self.url, self.error = "starting", None, None
            try:
                self.process = await asyncio.create_subprocess_exec(
                    binary,
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    stdin=asyncio.subprocess.DEVNULL,
                    env=env,
                )
            except OSError:
                self._cleanup_config()
                self.status, self.error = "error", "launch_failed"
                return self.snapshot()
            self.monitor = asyncio.create_task(self._watch(payload.hostname))
            return self.snapshot()

    async def _watch(self, hostname: str | None) -> None:
        process = self.process
        assert process is not None and process.stdout is not None

        async def read_output() -> None:
            assert process.stdout is not None
            discovered_url: str | None = None
            edge_connected = False
            while line := await process.stdout.readline():
                text = line.decode("utf-8", errors="replace")
                assert self.provider is not None
                url = public_url(self.provider, text)
                if self.provider == "cloudflare":
                    if url:
                        discovered_url = url
                    if "Registered tunnel connection" in text:
                        edge_connected = True
                    if self.mode == "managed-remote":
                        discovered_url = f"https://{hostname}"
                    url = discovered_url if edge_connected else None
                if url and self.status in {"starting", "running"}:
                    self.url, self.status = url, "running"

        reader = asyncio.create_task(read_output())
        try:
            async with asyncio.timeout(STARTUP_TIMEOUT):
                while self.status == "starting" and process.returncode is None:
                    if reader.done():
                        await reader
                        break
                    await asyncio.sleep(0.1)
                if self.status == "starting":
                    await process.wait()
            await reader
            await process.wait()
            self.url, self.status, self.error = None, "error", "process_exited"
        except TimeoutError:
            self.url, self.status, self.error = None, "error", "startup_timeout"
        except (ValueError, OSError):
            self.url, self.status, self.error = None, "error", "process_exited"
        finally:
            await terminate_process(process)
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
            self._cleanup_config()

    def _cleanup_config(self) -> None:
        if self.config_dir:
            self.config_dir.cleanup()
            self.config_dir = None

    async def _stop(self) -> None:
        if self.monitor:
            self.monitor.cancel()
            await asyncio.gather(self.monitor, return_exceptions=True)
        # A monitor cancelled before its first turn never enters its cleanup block.
        if self.process:
            await terminate_process(self.process)
        self._cleanup_config()
        self.process, self.monitor = None, None
        self.status, self.url, self.error = "stopped", None, None

    async def stop(self) -> dict:
        async with self.lock:
            await self._stop()
            return self.snapshot()
