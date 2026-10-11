import httpx
import pytest
import respx

from app.models.registry import AdapterRegistry


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("base_url", "expected_url"),
    [
        ("https://gateway.example", "https://gateway.example/models"),
        ("https://gateway.example/v1/", "https://gateway.example/v1/models"),
        ("https://gateway.example/openai", "https://gateway.example/openai/models"),
        ("https://gateway.example/v2/", "https://gateway.example/v2/models"),
    ],
)
@pytest.mark.parametrize(
    "method_name", ["get_llm_models", "get_embedding_models", "get_rerank_models"]
)
@respx.mock
async def test_openai_compatible_adapter_uses_configured_base_url(
    base_url: str, expected_url: str, method_name: str
) -> None:
    route = respx.get(expected_url).mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "test-model", "name": "Test Model"}]},
        )
    )
    adapter = AdapterRegistry.get_adapter("openai-compatible")

    async with httpx.AsyncClient() as client:
        models = await getattr(adapter, method_name)(client, base_url, "test-key")

    assert models == [{"id": "test-model", "name": "Test Model"}]
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_openai_compatible_adapter_sends_custom_headers() -> None:
    route = respx.get("https://gateway.example/models").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "test-model", "name": "Test Model"}]},
        )
    )
    adapter = AdapterRegistry.get_adapter("openai-compatible")

    async with httpx.AsyncClient() as client:
        await adapter.get_llm_models(
            client,
            "https://gateway.example",
            "test-key",
            headers={"X-Provider-Token": "custom-token"},
        )

    assert route.calls[0].request.headers["authorization"] == "Bearer test-key"
    assert route.calls[0].request.headers["x-provider-token"] == "custom-token"
