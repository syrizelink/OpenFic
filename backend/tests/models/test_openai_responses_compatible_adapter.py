import httpx
import pytest

from app.models.registry import AdapterRegistry


class _RecordingClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, str]]] = []

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        headers = kwargs.get("headers")
        self.requests.append((url, headers if isinstance(headers, dict) else {}))
        return httpx.Response(
            200,
            json={"data": [{"id": "responses-model", "name": "Responses Model"}]},
            request=httpx.Request("GET", url),
        )


@pytest.mark.asyncio
async def test_openai_responses_compatible_adapter_discovers_llm_models_only() -> None:
    adapter = AdapterRegistry.get_adapter("openai-compatible-responses")
    client = _RecordingClient()

    models = await adapter.get_llm_models(
        client,  # type: ignore[arg-type]
        "https://gateway.example",
        "test-key",
        headers={"X-Provider-Token": "custom-token"},
    )

    assert adapter.provider_type == "openai-compatible-responses"
    assert adapter.supports_llm()
    assert not adapter.supports_embedding()
    assert not adapter.supports_rerank()
    assert models == [{"id": "responses-model", "name": "Responses Model"}]
    assert client.requests == [
        (
            "https://gateway.example/v1/models",
            {
                "Authorization": "Bearer test-key",
                "X-Provider-Token": "custom-token",
            },
        )
    ]
