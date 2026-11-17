import httpx
import pytest
import respx
from langchain_openai import ChatOpenAI

from app.models.adapters.uberllm import UberLLMAdapter
from app.models.catalog.service import ModelProviderCatalogService
from app.models.clients.model_factory import ModelConfig, create_chat_model
from app.models.registry import AdapterRegistry
from app.models.services.model_provider_service import (
    _get_model_discovery_provider_type,
)

_BASE_URL = "https://api.uberllm.dev/v1"
_APP_ATTRIBUTION_HEADERS = {
    "HTTP-Referer": "https://github.com/syrizelink/OpenFic",
    "X-Title": "OpenFic",
}


def test_uberllm_uses_dedicated_adapter_for_model_discovery() -> None:
    runtime_provider_type = _get_model_discovery_provider_type("uberllm")

    assert isinstance(
        AdapterRegistry.get_adapter(runtime_provider_type), UberLLMAdapter
    )
    assert AdapterRegistry.get_supported_task_types("uberllm") == ["llm"]


@pytest.mark.asyncio
async def test_uberllm_is_a_local_catalog_provider() -> None:
    provider = await ModelProviderCatalogService().get_provider("uberllm")

    assert provider.display_name == "UberLLM"
    assert provider.api == provider.default_url == _BASE_URL
    assert provider.supported_task_types == ["llm"]
    assert provider.icon_path == "/icons/model/catalog/uberllm.svg"


def test_create_chat_model_uberllm_adds_app_attribution() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="uberllm",
            base_url=_BASE_URL,
            api_key="ull_test",
            model_id="deepseek/deepseek-v4.1-flash",
        )
    )

    assert isinstance(model, ChatOpenAI)
    assert model.default_headers is not None
    for name, value in _APP_ATTRIBUTION_HEADERS.items():
        assert model.default_headers[name] == value


@pytest.mark.asyncio
@respx.mock
async def test_uberllm_model_discovery_uses_display_names() -> None:
    route = respx.get(f"{_BASE_URL}/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "deepseek/deepseek-v4.1-flash",
                        "display_name": "DeepSeek V4.1 Flash",
                    },
                    {"id": "qwen/qwen3-32b"},
                    {"display_name": "missing id"},
                ]
            },
        )
    )

    async with httpx.AsyncClient() as client:
        models = await UberLLMAdapter().get_llm_models(client, _BASE_URL, "ull_test")

    assert models == [
        {"id": "deepseek/deepseek-v4.1-flash", "name": "DeepSeek V4.1 Flash"},
        {"id": "qwen/qwen3-32b", "name": "qwen/qwen3-32b"},
    ]
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer ull_test"
    for name, value in _APP_ATTRIBUTION_HEADERS.items():
        assert request.headers[name] == value


@pytest.mark.asyncio
@respx.mock
async def test_uberllm_model_discovery_raises_on_invalid_key() -> None:
    respx.get(f"{_BASE_URL}/models").mock(return_value=httpx.Response(401))

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await UberLLMAdapter().get_llm_models(client, _BASE_URL, "invalid")


@pytest.mark.asyncio
async def test_uberllm_has_no_embedding_models() -> None:
    async with httpx.AsyncClient() as client:
        assert await UberLLMAdapter().get_embedding_models(client, _BASE_URL, "ull_test") == []
