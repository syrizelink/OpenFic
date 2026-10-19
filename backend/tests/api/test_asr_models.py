"""Model preparation verifies pinned files and never publishes partial downloads."""

import asyncio
import hashlib

import httpx
import pytest
import respx
from fastapi import HTTPException

from app.asr import models
from app.asr.config import ProviderConfig


@pytest.fixture
def assets(monkeypatch, tmp_path):
    data = b"verified model"
    manifest = {
        key: {
            "name": name,
            "url": f"https://models.example/{name}",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for key, name in [
            ("model_path", "model.onnx"),
            ("tokens_path", "tokens.txt"),
            ("vad_path", "vad.onnx"),
        ]
    }
    monkeypatch.setattr(models, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(models, "ASSETS", manifest)
    return tmp_path, manifest, data


async def test_explicit_preparation_reuses_only_verified_files(assets):
    root, manifest, data = assets
    with respx.mock as mock:
        routes = [
            mock.get(asset["url"]).mock(return_value=httpx.Response(200, content=data))
            for asset in manifest.values()
        ]
        assert not models.ready(ProviderConfig())
        await models.prepare(ProviderConfig())
        assert models.ready(ProviderConfig())
        await models.prepare(ProviderConfig())
        assert all(route.call_count == 1 for route in routes)
        (root / "model.onnx").write_bytes(b"corrupt")
        assert not models.ready(ProviderConfig())
        await models.prepare(ProviderConfig())
        assert routes[0].call_count == 2
        assert models.ready(ProviderConfig())


@pytest.mark.parametrize("content", [b"short", b"x" * 100, b"invalid model!"])
async def test_corrupt_downloads_never_publish(assets, content):
    root, manifest, _ = assets
    with respx.mock as mock:
        mock.get(manifest["model_path"]["url"]).mock(
            return_value=httpx.Response(200, content=content)
        )
        with pytest.raises(HTTPException) as error:
            await models.prepare(ProviderConfig())
    assert error.value.status_code == 502
    assert list(root.iterdir()) == []


async def test_explicit_offline_paths_do_not_download(assets):
    root, manifest, data = assets
    config = ProviderConfig(
        **{key: str(root / asset["name"]) for key, asset in manifest.items()}
    )
    for path in models.paths(config).values():
        path.write_bytes(data)
    with respx.mock(assert_all_mocked=True):
        await models.prepare(config)
        assert models.resolve_paths(config) == config.model_dump(include=set(manifest))


async def test_cancelled_download_removes_partial_file(assets):
    root, manifest, _ = assets

    class CancelledStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"partial"
            raise asyncio.CancelledError()

    with respx.mock as mock:
        mock.get(manifest["model_path"]["url"]).mock(
            return_value=httpx.Response(200, stream=CancelledStream())
        )
        with pytest.raises(asyncio.CancelledError):
            await models.prepare(ProviderConfig())
    assert list(root.iterdir()) == []
