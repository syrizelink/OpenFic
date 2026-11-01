"""Runcrate discovery and requests use the documented OpenAI-compatible endpoints."""

import json

import pytest
import respx
from httpx import Response
from langchain_core.messages import HumanMessage

from app.core.encryption import EncryptionService
from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig
from app.models.clients.model_factory import ModelConfig, create_chat_model
from app.models.entities.model_provider import ModelProvider
from app.models.services.model_provider_service import ModelProviderService


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("task_type", ["llm", "embedding"])
async def test_runcrate_discovers_account_models(task_type: str) -> None:
    route = respx.get("https://api.runcrate.ai/v1/models").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {"id": "deepseek-ai/DeepSeek-V4-Flash"},
                    {"id": "Qwen/Qwen3-Embedding-8B"},
                ]
            },
        )
    )
    encryption = EncryptionService("id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ=")
    service = ModelProviderService(encryption)
    provider = ModelProvider(
        name="Runcrate",
        provider_type="runcrate",
        url="https://api.runcrate.ai/v1",
        api_key_encrypted=encryption.encrypt("test-key"),
    )
    models = await service.get_available_models(provider, task_type)
    assert [model["id"] for model in models] == [
        "deepseek-ai/DeepSeek-V4-Flash",
        "Qwen/Qwen3-Embedding-8B",
    ]
    assert route.calls[0].request.headers["authorization"] == "Bearer test-key"


@pytest.mark.asyncio
@respx.mock
async def test_runcrate_chat_request() -> None:
    route = respx.post("https://api.runcrate.ai/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chat-test",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-ai/DeepSeek-V4-Flash",
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
            provider_type="runcrate",
            base_url="https://api.runcrate.ai/v1",
            api_key="test-key",
            model_id="deepseek-ai/DeepSeek-V4-Flash",
        )
    )
    response = await model.ainvoke([HumanMessage(content="Hi")])
    assert response.content == "Hello"
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer test-key"
    assert json.loads(request.content)["model"] == "deepseek-ai/DeepSeek-V4-Flash"


@pytest.mark.asyncio
@respx.mock
async def test_runcrate_embedding_request() -> None:
    route = respx.post("https://api.runcrate.ai/v1/embeddings").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {"object": "embedding", "index": 0, "embedding": [0.1, 0.2]},
                ],
                "model": "Qwen/Qwen3-Embedding-8B",
            },
        )
    )
    client = EmbeddingClient(
        EmbeddingConfig(
            provider_type="runcrate",
            base_url="https://api.runcrate.ai/v1",
            api_key="test-key",
            model_id="Qwen/Qwen3-Embedding-8B",
        )
    )
    response = await client.embed(["Hello"])
    assert response.embeddings == [[0.1, 0.2]]
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer test-key"
    assert json.loads(request.content)["model"] == "Qwen/Qwen3-Embedding-8B"
