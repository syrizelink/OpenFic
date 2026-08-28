import httpx
import pytest

from app.models.registry import AdapterRegistry


class _RecordingClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, object, dict[str, str]]] = []

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        params = kwargs.get("params")
        headers = kwargs.get("headers")
        self.requests.append(
            (url, params, headers if isinstance(headers, dict) else {})
        )
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-2.5-flash",
                        "displayName": "Gemini 2.5 Flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/text-embedding-004",
                        "displayName": "Text Embedding 004",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                    {
                        "name": "models/legacy-model",
                        "displayName": "Legacy Model",
                        "supportedGenerationMethods": None,
                    },
                ]
            },
            request=httpx.Request("GET", url),
        )


@pytest.mark.asyncio
async def test_gemini_compatible_adapter_discovers_llm_models_from_native_endpoint() -> None:
    adapter = AdapterRegistry.get_adapter("gemini-compatible")
    client = _RecordingClient()

    models = await adapter.get_llm_models(
        client,  # type: ignore[arg-type]
        "https://gateway.example",
        "test-key",
        headers={"X-Provider-Token": "custom-token"},
    )

    assert adapter.provider_type == "gemini-compatible"
    assert adapter.supports_llm()
    assert not adapter.supports_embedding()
    assert not adapter.supports_rerank()
    assert models == [
        {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
        {"id": "legacy-model", "name": "Legacy Model"},
    ]
    assert client.requests == [
        (
            "https://gateway.example/v1beta/models",
            None,
            {
                "x-goog-api-key": "test-key",
                "X-Provider-Token": "custom-token",
            },
        )
    ]


@pytest.mark.asyncio
async def test_gemini_compatible_adapter_does_not_discover_embedding_models() -> None:
    adapter = AdapterRegistry.get_adapter("gemini-compatible")

    models = await adapter.get_embedding_models(
        _RecordingClient(),  # type: ignore[arg-type]
        "https://gateway.example",
        "test-key",
    )

    assert models == []
