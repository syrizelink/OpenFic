import httpx
import pytest

from app.models.registry import AdapterRegistry


class _RecordingClient:
    def __init__(self) -> None:
        self.urls: list[str] = []

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        self.urls.append(url)
        return httpx.Response(
            200,
            json={"data": [{"id": "unexpected-model"}]},
            request=httpx.Request("GET", url),
        )


@pytest.mark.asyncio
async def test_anthropic_compatible_adapter_only_supports_llm_without_model_discovery() -> None:
    adapter = AdapterRegistry.get_adapter("anthropic-compatible")
    client = _RecordingClient()

    models = await adapter.get_llm_models(
        client,  # type: ignore[arg-type]
        "https://gateway.example/v1",
        "test-key",
    )

    assert adapter.provider_type == "anthropic-compatible"
    assert adapter.supports_llm()
    assert not adapter.supports_embedding()
    assert not adapter.supports_rerank()
    assert models == []
    assert client.urls == []
