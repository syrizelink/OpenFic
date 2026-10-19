"""Explicit preparation of revision-pinned SenseVoice resources."""

import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import aiofiles
import httpx
from fastapi import HTTPException

from app.asr.config import ProviderConfig
from app.settings import BACKEND_DATA_DIR

ASSETS = json.loads(Path(__file__).with_name("sensevoice-assets.json").read_text())
ASSETS = {
    "model_path": ASSETS["models"]["int8"],
    "tokens_path": ASSETS["tokens"],
    "vad_path": ASSETS["vad"],
}
MODEL_DIR = BACKEND_DATA_DIR / "asr" / "sensevoice"


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


async def prepare(config: ProviderConfig) -> None:
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        for key, path in paths(config).items():
            if getattr(config, key):
                if not path.is_absolute() or not path.is_file():
                    raise HTTPException(
                        400, "Custom model paths must point to existing absolute files"
                    )
                continue
            asset = ASSETS[key]
            if await asyncio.to_thread(matches, path, asset):
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(f".{uuid4().hex}.part")
            try:
                digest, size = hashlib.sha256(), 0
                async with client.stream("GET", asset["url"]) as response:
                    response.raise_for_status()
                    async with aiofiles.open(partial, "wb") as output:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            size += len(chunk)
                            if size > asset["bytes"]:
                                raise HTTPException(502, "Model download size mismatch")
                            digest.update(chunk)
                            await output.write(chunk)
                if size != asset["bytes"] or digest.hexdigest() != asset["sha256"]:
                    raise HTTPException(502, "Model download checksum mismatch")
                partial.replace(path)
            finally:
                partial.unlink(missing_ok=True)
