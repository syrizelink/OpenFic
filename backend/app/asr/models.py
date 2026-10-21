"""Explicit preparation of revision-pinned SenseVoice resources."""

import asyncio
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import aiofiles
import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from app.asr.config import ProviderConfig
from app.settings import BACKEND_DATA_DIR

ASSETS = json.loads(Path(__file__).with_name("sensevoice-assets.json").read_text())
ASSETS = {
    "model_path": ASSETS["models"]["int8"],
    "tokens_path": ASSETS["tokens"],
    "vad_path": ASSETS["vad"],
}
MODEL_DIR = BACKEND_DATA_DIR / "asr" / "sensevoice"
SOURCES = {"huggingface": "huggingface.co", "hf-mirror": "hf-mirror.com"}
SOURCE_PROBE_TIMEOUT = 5


class PreparationProgress(BaseModel):
    status: Literal[
        "idle", "selecting_source", "downloading", "verifying", "ready", "failed"
    ] = "idle"
    downloaded_bytes: int = 0
    total_bytes: int = 0
    file_name: str = ""
    source: str = ""


async def order_model_sources(client: httpx.AsyncClient, url: str) -> list[str]:
    """Race bounded HEAD probes, retain alternatives and tolerate HEAD refusals."""
    parsed = urlsplit(url)
    names = list(SOURCES)
    urls = [
        urlunsplit(("https", SOURCES[name], parsed.path, parsed.query, ""))
        for name in names
    ]
    if len(urls) == 1:
        return urls

    async def probe(candidate: str) -> str:
        response = await client.head(candidate, timeout=SOURCE_PROBE_TIMEOUT)
        response.raise_for_status()
        return candidate

    tasks = [asyncio.create_task(probe(candidate)) for candidate in urls]
    preferred = None
    try:
        async with asyncio.timeout(SOURCE_PROBE_TIMEOUT):
            for finished in asyncio.as_completed(tasks):
                try:
                    preferred = await finished
                    break
                except httpx.HTTPError:
                    continue
    except TimeoutError:
        pass  # Some hosts refuse HEAD while GET still works.
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return (
        [preferred, *(candidate for candidate in urls if candidate != preferred)]
        if preferred
        else urls
    )


def paths(config: ProviderConfig) -> dict[str, Path]:
    return {
        key: Path(getattr(config, key) or MODEL_DIR / asset["name"])
        for key, asset in ASSETS.items()
    }


def resolve_paths(config: ProviderConfig) -> dict[str, str]:
    result = paths(config)
    if not ready(config):
        raise HTTPException(
            409,
            "Prepare the SenseVoice model first, or configure existing model, tokens and VAD paths",
        )
    return {key: str(path) for key, path in result.items()}


def ready(config: ProviderConfig) -> bool:
    try:
        return all(
            (path.is_file() and path.stat().st_size > 0)
            if getattr(config, key)
            else matches(path, ASSETS[key])
            for key, path in paths(config).items()
        )
    except OSError:
        return False


def matches(path: Path, asset: dict) -> bool:
    if not path.is_file() or path.stat().st_size != asset["bytes"]:
        return False
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest() == asset["sha256"]


async def prepare(
    config: ProviderConfig,
    on_progress: Callable[[PreparationProgress], None] = lambda _: None,
) -> None:
    targets = paths(config)
    progress = PreparationProgress(
        status="verifying",
        total_bytes=sum(
            asset["bytes"] for key, asset in ASSETS.items() if not getattr(config, key)
        ),
    )

    def report(**changes):
        nonlocal progress
        progress = progress.model_copy(update=changes)
        on_progress(progress)

    report()
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        for key, path in targets.items():
            if getattr(config, key):
                if (
                    not path.is_absolute()
                    or not path.is_file()
                    or path.stat().st_size == 0
                ):
                    raise HTTPException(
                        400, "Custom model paths must point to existing absolute files"
                    )
                continue
            asset = ASSETS[key]
            completed = progress.downloaded_bytes
            report(status="verifying", file_name=asset["name"], source="")
            if await asyncio.to_thread(matches, path, asset):
                report(downloaded_bytes=completed + asset["bytes"])
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            report(status="selecting_source")
            urls = await order_model_sources(client, asset["url"])
            for index, url in enumerate(urls):
                partial = path.with_suffix(f".{uuid4().hex}.part")
                report(
                    status="downloading",
                    source=urlsplit(url).netloc,
                    downloaded_bytes=completed,
                )
                try:
                    digest, size = hashlib.sha256(), 0
                    async with client.stream("GET", url) as response:
                        response.raise_for_status()
                        async with aiofiles.open(partial, "wb") as output:
                            async for chunk in response.aiter_bytes(64 * 1024):
                                size += len(chunk)
                                if size > asset["bytes"]:
                                    raise HTTPException(
                                        502, "Model download size mismatch"
                                    )
                                digest.update(chunk)
                                await output.write(chunk)
                                report(downloaded_bytes=completed + size)
                    report(status="verifying")
                    if size != asset["bytes"] or digest.hexdigest() != asset["sha256"]:
                        raise HTTPException(502, "Model download checksum mismatch")
                    partial.replace(path)
                    break
                except (httpx.HTTPError, HTTPException):
                    if index == len(urls) - 1:
                        raise
                finally:
                    partial.unlink(missing_ok=True)
    report(
        status="ready", downloaded_bytes=progress.total_bytes, file_name="", source=""
    )
