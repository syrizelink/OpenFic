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
            "url": f"https://huggingface.co/test/resolve/pinned/{name}",
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
        await models.prepare(ProviderConfig(download_source="huggingface"))
        assert models.ready(ProviderConfig())
        await models.prepare(ProviderConfig(download_source="huggingface"))
        assert all(route.call_count == 1 for route in routes)
        (root / "model.onnx").write_bytes(b"corrupt")
        assert not models.ready(ProviderConfig())
        await models.prepare(ProviderConfig(download_source="huggingface"))
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
            await models.prepare(ProviderConfig(download_source="huggingface"))
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
            await models.prepare(ProviderConfig(download_source="huggingface"))
    assert list(root.iterdir()) == []


async def test_auto_source_prefers_first_response_and_cancels_other_probe():
    cancelled = asyncio.Event()
    started = asyncio.Event()
    url = "https://huggingface.co/repo/resolve/pinned/model.onnx"
    mirror = url.replace("huggingface.co", "hf-mirror.com")

    async def slow(_):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def fast(_):
        await started.wait()
        return httpx.Response(200)

    with respx.mock as mock:
        mock.head(url).mock(side_effect=slow)
        mock.head(mirror).mock(side_effect=fast)
        async with httpx.AsyncClient() as client:
            assert await models.order_model_sources(client, url, "auto") == [
                mirror,
                url,
            ]
    assert cancelled.is_set()


async def test_failed_or_timed_out_probes_preserve_order(monkeypatch):
    monkeypatch.setattr(models, "SOURCE_PROBE_TIMEOUT", 0.01)
    url = "https://huggingface.co/repo/resolve/pinned/model.onnx"
    mirror = url.replace("huggingface.co", "hf-mirror.com")

    async def stalled(_):
        await asyncio.Event().wait()

    with respx.mock as mock:
        mock.head(url).mock(return_value=httpx.Response(405))
        mock.head(mirror).mock(side_effect=stalled)
        async with httpx.AsyncClient() as client:
            assert await models.order_model_sources(client, url, "auto") == [
                url,
                mirror,
            ]


@pytest.mark.parametrize(
    "source,host", [("huggingface", "huggingface.co"), ("hf-mirror", "hf-mirror.com")]
)
async def test_explicit_source_skips_probes_and_reports_verified_progress(
    assets, source, host
):
    _, manifest, data = assets
    events = []
    with respx.mock as mock:
        routes = [
            mock.get(asset["url"].replace("huggingface.co", host)).mock(
                return_value=httpx.Response(200, content=data)
            )
            for asset in manifest.values()
        ]
        await models.prepare(ProviderConfig(download_source=source), events.append)
    assert all(route.called for route in routes)
    assert events[-1].status == "ready"
    assert events[-1].downloaded_bytes == events[-1].total_bytes == 3 * len(data)
    assert all(event.source in {"", host} for event in events)
    assert [event.downloaded_bytes for event in events] == sorted(
        event.downloaded_bytes for event in events
    )
    assert any(event.status == "verifying" for event in events)


@pytest.mark.parametrize("failure", ["http", "integrity", "network"])
async def test_auto_download_falls_back_and_keeps_verified_cache(assets, failure):
    root, manifest, data = assets
    events = []
    with respx.mock as mock:
        for asset in manifest.values():
            mock.head(asset["url"]).mock(return_value=httpx.Response(405))
            mock.head(asset["url"].replace("huggingface.co", "hf-mirror.com")).mock(
                return_value=httpx.Response(405)
            )
            mock.get(asset["url"]).mock(return_value=httpx.Response(200, content=data))
        primary = mock.get(manifest["model_path"]["url"])
        if failure == "network":
            primary.mock(side_effect=httpx.ConnectError("offline"))
        else:
            primary.mock(
                return_value=httpx.Response(
                    503 if failure == "http" else 200, content=b"corrupt"
                )
            )
        mirror = mock.get(
            manifest["model_path"]["url"].replace("huggingface.co", "hf-mirror.com")
        ).mock(return_value=httpx.Response(200, content=data))
        await models.prepare(ProviderConfig(), events.append)
        assert primary.called and mirror.called
        assert models.ready(ProviderConfig())
        assert not list(root.glob("*.part"))
        assert any(
            event.source == "hf-mirror.com" and event.downloaded_bytes == len(data)
            for event in events
        )
        mock.reset()
        await models.prepare(ProviderConfig(), events.append)
        assert not mock.calls  # Verified files need neither probes nor downloads.


async def test_progress_counts_cached_files_and_excludes_custom_files(assets):
    root, manifest, data = assets
    (root / manifest["model_path"]["name"]).write_bytes(data)
    custom = root / "custom-tokens.txt"
    custom.write_bytes(b"custom tokens")
    events = []
    with respx.mock as mock:
        mock.get(manifest["vad_path"]["url"]).mock(
            return_value=httpx.Response(200, content=data)
        )
        await models.prepare(
            ProviderConfig(download_source="huggingface", tokens_path=str(custom)),
            events.append,
        )
    assert events[-1].total_bytes == 2 * len(data)
    assert events[-1].downloaded_bytes == events[-1].total_bytes


async def test_streaming_reports_intermediate_bytes_before_completion(
    assets, monkeypatch
):
    _, manifest, _ = assets
    data = b"x" * (3 * 64 * 1024)
    asset = {
        **manifest["model_path"],
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    monkeypatch.setattr(models, "ASSETS", {"model_path": asset})
    events = []

    class Chunks(httpx.AsyncByteStream):
        async def __aiter__(self):
            for offset in range(0, len(data), 64 * 1024):
                yield data[offset : offset + 64 * 1024]
                await asyncio.sleep(0)

    with respx.mock as mock:
        mock.get(asset["url"]).mock(return_value=httpx.Response(200, stream=Chunks()))
        await models.prepare(
            ProviderConfig(download_source="huggingface"), events.append
        )
    assert [
        event.downloaded_bytes for event in events if event.status == "downloading"
    ] == [0, 65536, 131072, 196608]
    assert events[-1].status == "ready"
