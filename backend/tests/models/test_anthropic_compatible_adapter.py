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
@pytest.mark.parametrize(
    ("base_url", "expected_url"),
    [
        ("https://gateway.example/anthropic", "https://gateway.example/v1/models"),
        ("https://gateway.example/claude/", "https://gateway.example/v1/models"),
        ("https://gateway.example/v1/anthropic", "https://gateway.example/v1/models"),
        ("https://gateway.example/v1/claude/", "https://gateway.example/v1/models"),
        ("https://gateway.example/v1/", "https://gateway.example/v1/models"),
    ],
)
async def test_anthropic_compatible_adapter_discovers_models_from_v1_endpoint(
    base_url: str, expected_url: str
) -> None:
    adapter = AdapterRegistry.get_adapter("anthropic-compatible")
    client = _RecordingClient()

    models = await adapter.get_llm_models(
        client,  # type: ignore[arg-type]
        base_url,
        "test-key",
    )

    assert adapter.provider_type == "anthropic-compatible"
    assert adapter.supports_llm()
    assert not adapter.supports_embedding()
    assert not adapter.supports_rerank()
    assert models == [{"id": "unexpected-model", "name": "unexpected-model"}]
    assert client.urls == [expected_url]
