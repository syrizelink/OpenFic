import httpx
import pytest
import respx

from app.models.adapters.openrouter import OpenRouterAdapter
from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig
from app.models.clients.model_factory import ModelConfig, create_chat_model
from app.models.clients.rerank_client import RerankClient, RerankConfig


_APP_ATTRIBUTION_HEADERS = {
    "HTTP-Referer": "https://github.com/syrizelink/OpenFic",
    "X-OpenRouter-Title": "OpenFic",
    "X-OpenRouter-Categories": "creative-writing,writing-assistant",
}


def test_create_chat_model_openrouter_adds_app_attribution() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-test",
            model_id="openai/gpt-5.2",
        )
    )

    assert model.app_url == "https://github.com/syrizelink/OpenFic"
    assert model.app_title == "OpenFic"
    assert model.app_categories == ["creative-writing", "writing-assistant"]


def test_openrouter_embeddings_add_app_attribution() -> None:
    client = EmbeddingClient(
        EmbeddingConfig(
            provider_type="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-test",
            model_id="openai/text-embedding-3-small",
        )
    )

    embeddings = client._get_embeddings()

    assert embeddings.default_headers == _APP_ATTRIBUTION_HEADERS  # type: ignore[attr-defined]


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_model_discovery_sends_app_attribution() -> None:
    route = respx.get("https://openrouter.ai/api/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    async with httpx.AsyncClient() as client:
        models = await OpenRouterAdapter().get_llm_models(
            client, "https://openrouter.ai/api/v1", "sk-or-test"
        )

    assert models == []
    for name, value in _APP_ATTRIBUTION_HEADERS.items():
        assert route.calls[0].request.headers[name] == value


@pytest.mark.asyncio
@respx.mock
async def test_openrouter_rerank_sends_app_attribution() -> None:
    route = respx.post("https://openrouter.ai/api/v1/rerank").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "test-reranker",
                "results": [{"index": 0, "relevance_score": 0.9}],
            },
        )
    )
    client = RerankClient(
        RerankConfig(
            provider_type="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-test",
            model_id="test-reranker",
        )
    )

    await client.rerank("query", ["document"])

    for name, value in _APP_ATTRIBUTION_HEADERS.items():
        assert route.calls[0].request.headers[name] == value
