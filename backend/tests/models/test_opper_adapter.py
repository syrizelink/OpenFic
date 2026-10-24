import httpx
import pytest
import respx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.models.adapters.opper import OpperAdapter
from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig
from app.models.clients.model_factory import ModelConfig, create_chat_model
from app.models.registry import AdapterRegistry
from app.models.services.model_provider_service import (
    _get_model_discovery_provider_type,
)

_BASE_URL = "https://api.opper.ai/v3/compat"
_APP_ATTRIBUTION_HEADERS = {"X-Opper-Name": "openfic"}
_MODELS = [
    {
        "id": "claude-sonnet-4-6",
        "opper": {"type": "llm", "display_name": "Claude Sonnet 4.6"},
    },
    {"id": "anthropic/claude-sonnet-4-6", "opper": {"type": "llm"}},
    {"id": "text-embedding-3-small", "opper": {"type": "embedding"}},
    {"id": "gpt-image-2", "opper": {"type": "image"}},
]


def test_opper_uses_dedicated_adapter_for_model_discovery() -> None:
    runtime_provider_type = _get_model_discovery_provider_type("opper")

    assert isinstance(AdapterRegistry.get_adapter(runtime_provider_type), OpperAdapter)
    assert AdapterRegistry.get_supported_task_types("opper") == ["llm", "embedding"]


def test_create_chat_model_opper_adds_app_attribution() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="opper",
            base_url=_BASE_URL,
            api_key="op-test",
            model_id="claude-sonnet-4-6",
        )
    )

    assert isinstance(model, ChatOpenAI)
    assert model.default_headers is not None
    for name, value in _APP_ATTRIBUTION_HEADERS.items():
        assert model.default_headers[name] == value


def test_opper_embeddings_add_app_attribution() -> None:
    client = EmbeddingClient(
        EmbeddingConfig(
            provider_type="opper",
            base_url=_BASE_URL,
            api_key="op-test",
            model_id="text-embedding-3-small",
        )
    )

    embeddings = client._get_embeddings()

    assert isinstance(embeddings, OpenAIEmbeddings)
    assert embeddings.default_headers == _APP_ATTRIBUTION_HEADERS


@pytest.mark.asyncio
@respx.mock
async def test_opper_model_discovery_lists_chat_models() -> None:
    models_route = respx.get(f"{_BASE_URL}/models").mock(
        return_value=httpx.Response(200, json={"data": _MODELS})
    )

    async with httpx.AsyncClient() as client:
        models = await OpperAdapter().get_llm_models(client, _BASE_URL, "op-test")

    assert models == [
        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"},
        {"id": "anthropic/claude-sonnet-4-6", "name": "anthropic/claude-sonnet-4-6"},
    ]
    request = models_route.calls[0].request
    assert request.headers["Authorization"] == "Bearer op-test"
    for name, value in _APP_ATTRIBUTION_HEADERS.items():
        assert request.headers[name] == value


@pytest.mark.asyncio
@respx.mock
async def test_opper_model_discovery_raises_on_invalid_key() -> None:
    respx.get(f"{_BASE_URL}/models").mock(return_value=httpx.Response(401))

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await OpperAdapter().get_llm_models(client, _BASE_URL, "invalid")


@pytest.mark.asyncio
@respx.mock
async def test_opper_embedding_discovery_filters_embedding_models() -> None:
    respx.get(f"{_BASE_URL}/models").mock(
        return_value=httpx.Response(200, json={"data": _MODELS})
    )

    async with httpx.AsyncClient() as client:
        models = await OpperAdapter().get_embedding_models(client, _BASE_URL, "op-test")

    assert models == [
        {"id": "text-embedding-3-small", "name": "text-embedding-3-small"}
    ]
