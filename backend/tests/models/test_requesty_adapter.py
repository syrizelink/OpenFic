import httpx
import pytest
import respx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.models.adapters.requesty import RequestyAdapter
from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig
from app.models.clients.model_factory import ModelConfig, create_chat_model
from app.models.registry import AdapterRegistry
from app.models.services.model_provider_service import (
    _get_model_discovery_provider_type,
)

_BASE_URL = "https://router.requesty.ai/v1"
_APP_ATTRIBUTION_HEADERS = {
    "HTTP-Referer": "https://github.com/syrizelink/OpenFic",
    "X-Title": "OpenFic",
}


def test_requesty_uses_dedicated_adapter_for_model_discovery() -> None:
    runtime_provider_type = _get_model_discovery_provider_type("requesty")

    assert isinstance(
        AdapterRegistry.get_adapter(runtime_provider_type), RequestyAdapter
    )
    assert AdapterRegistry.get_supported_task_types("requesty") == ["llm", "embedding"]


def test_create_chat_model_requesty_adds_app_attribution() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="requesty",
            base_url=_BASE_URL,
            api_key="rqsty-test",
            model_id="openai/gpt-4o-mini",
        )
    )

    assert isinstance(model, ChatOpenAI)
    assert model.default_headers is not None
    for name, value in _APP_ATTRIBUTION_HEADERS.items():
        assert model.default_headers[name] == value


def test_requesty_embeddings_add_app_attribution() -> None:
    client = EmbeddingClient(
        EmbeddingConfig(
            provider_type="requesty",
            base_url=_BASE_URL,
            api_key="rqsty-test",
            model_id="openai/text-embedding-3-small",
        )
    )

    embeddings = client._get_embeddings()

    assert isinstance(embeddings, OpenAIEmbeddings)
    assert embeddings.default_headers == _APP_ATTRIBUTION_HEADERS


@pytest.mark.asyncio
@respx.mock
async def test_requesty_model_discovery_lists_managed_models_first() -> None:
    managed_route = respx.get(f"{_BASE_URL}/models/managed").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "gpt-5.4-mini", "api": "chat"}]},
        )
    )
    models_route = respx.get(f"{_BASE_URL}/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "openai/gpt-4o-mini", "api": "chat"},
                    {"id": "gpt-5.4-mini", "api": "chat"},
                    {"id": "openai/text-embedding-3-small", "api": "embedding"},
                ]
            },
        )
    )

    async with httpx.AsyncClient() as client:
        models = await RequestyAdapter().get_llm_models(client, _BASE_URL, "rqsty-test")

    assert [model["id"] for model in models] == ["gpt-5.4-mini", "openai/gpt-4o-mini"]
    for route in (managed_route, models_route):
        request = route.calls[0].request
        assert request.headers["Authorization"] == "Bearer rqsty-test"
        for name, value in _APP_ATTRIBUTION_HEADERS.items():
            assert request.headers[name] == value


@pytest.mark.asyncio
@respx.mock
async def test_requesty_model_discovery_falls_back_when_managed_fails() -> None:
    respx.get(f"{_BASE_URL}/models/managed").mock(return_value=httpx.Response(500))
    respx.get(f"{_BASE_URL}/models").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "openai/gpt-4o-mini", "api": "chat"}]},
        )
    )

    async with httpx.AsyncClient() as client:
        models = await RequestyAdapter().get_llm_models(client, _BASE_URL, "rqsty-test")

    assert models == [{"id": "openai/gpt-4o-mini", "name": "openai/gpt-4o-mini"}]


@pytest.mark.asyncio
@respx.mock
async def test_requesty_model_discovery_raises_on_invalid_key() -> None:
    respx.get(f"{_BASE_URL}/models/managed").mock(return_value=httpx.Response(403))
    respx.get(f"{_BASE_URL}/models").mock(return_value=httpx.Response(403))

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await RequestyAdapter().get_llm_models(client, _BASE_URL, "invalid")


@pytest.mark.asyncio
@respx.mock
async def test_requesty_embedding_discovery_filters_embedding_models() -> None:
    respx.get(f"{_BASE_URL}/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "openai/gpt-4o-mini", "api": "chat"},
                    {"id": "openai/text-embedding-3-small", "api": "embedding"},
                ]
            },
        )
    )

    async with httpx.AsyncClient() as client:
        models = await RequestyAdapter().get_embedding_models(
            client, _BASE_URL, "rqsty-test"
        )

    assert models == [
        {"id": "openai/text-embedding-3-small", "name": "openai/text-embedding-3-small"}
    ]
