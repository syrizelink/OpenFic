"""Infistar discovery and requests use the documented OpenAI-compatible endpoints."""

import json

import pytest
import respx
from httpx import Response
from langchain_core.messages import HumanMessage

from app.core.encryption import EncryptionService
from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig
from app.models.clients.model_factory import ModelConfig, create_chat_model
from app.models.clients.rerank_client import RerankClient, RerankConfig
from app.models.entities.model_provider import ModelProvider
from app.models.services.model_provider_service import ModelProviderService


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("task_type", ["llm", "embedding", "rerank"])
async def test_infistar_discovers_account_models(task_type: str) -> None:
    route = respx.get("https://infistar.cc/v1/models").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {"id": "qwen-plus"},
                    {"id": "text-embedding-v4"},
                    {"id": "qwen3-rerank"},
                ]
            },
        )
    )
    encryption = EncryptionService("id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ=")
    service = ModelProviderService(encryption)
    provider = ModelProvider(
        name="Infistar",
        provider_type="infistar",
        url="https://infistar.cc/v1",
        api_key_encrypted=encryption.encrypt("test-key"),
    )
    models = await service.get_available_models(provider, task_type)
    assert [model["id"] for model in models] == [
        "qwen-plus",
        "text-embedding-v4",
        "qwen3-rerank",
    ]
    assert route.calls[0].request.headers["authorization"] == "Bearer test-key"


@pytest.mark.asyncio
@respx.mock
async def test_infistar_chat_request() -> None:
    route = respx.post("https://infistar.cc/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chat-test",
                "object": "chat.completion",
                "created": 0,
                "model": "qwen-plus",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )
    )
    model = create_chat_model(
        ModelConfig(
            provider_type="infistar",
            base_url="https://infistar.cc/v1",
            api_key="test-key",
            model_id="qwen-plus",
        )
    )
    response = await model.ainvoke([HumanMessage(content="Hi")])
    assert response.content == "Hello"
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer test-key"
    assert json.loads(request.content)["model"] == "qwen-plus"


@pytest.mark.asyncio
@respx.mock
async def test_infistar_embedding_request_supports_dimensions() -> None:
    route = respx.post("https://infistar.cc/v1/embeddings").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {"object": "embedding", "index": 0, "embedding": [0.1, 0.2]},
                ],
                "model": "text-embedding-v4",
            },
        )
    )
    client = EmbeddingClient(
        EmbeddingConfig(
            provider_type="infistar",
            base_url="https://infistar.cc/v1",
            api_key="test-key",
            model_id="text-embedding-v4",
            dimensions=2,
        )
    )
    response = await client.embed(["Hello"])
    assert response.embeddings == [[0.1, 0.2]]
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer test-key"
    assert json.loads(request.content) == {
        "model": "text-embedding-v4",
        "input": ["Hello"],
        "encoding_format": "float",
        "dimensions": 2,
    }


@pytest.mark.asyncio
@respx.mock
async def test_infistar_rerank_request() -> None:
    route = respx.post("https://infistar.cc/v1/rerank").mock(
        return_value=Response(
            200,
            json={
                "results": [{"index": 1, "relevance_score": 0.9}],
            },
        )
    )
    client = RerankClient(
        RerankConfig(
            provider_type="infistar",
            base_url="https://infistar.cc/v1",
            api_key="test-key",
            model_id="qwen3-rerank",
        )
    )
    response = await client.rerank("query", ["first", "second"], top_n=1)
    assert [(item.index, item.relevance_score) for item in response.results] == [
        (1, 0.9)
    ]
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer test-key"
    assert json.loads(request.content) == {
        "model": "qwen3-rerank",
        "query": "query",
        "documents": ["first", "second"],
        "top_n": 1,
    }
