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


@pytest.mark.parametrize(
    ("method_name", "expected_models"),
    [
        (
            "get_llm_models",
            [
                {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
                {"id": "legacy-model", "name": "Legacy Model"},
            ],
        ),
        (
            "get_embedding_models",
            [{"id": "text-embedding-004", "name": "Text Embedding 004"}],
        ),
    ],
)
@pytest.mark.asyncio
async def test_google_genai_adapter_uses_header_and_ignores_null_methods(
    method_name: str,
    expected_models: list[dict[str, str]],
) -> None:
    adapter = AdapterRegistry.get_adapter("google-genai")
    client = _RecordingClient()

    models = await getattr(adapter, method_name)(
        client,  # type: ignore[arg-type]
        "https://gateway.example",
        "test-key",
    )

    assert models == expected_models
    assert client.requests == [
        (
            "https://gateway.example/v1beta/models",
            None,
            {"x-goog-api-key": "test-key"},
        )
    ]
