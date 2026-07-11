# -*- coding: utf-8 -*-
"""
FastEmbed client tests - 内置 fastembed 客户端的 provider 路由逻辑。

不依赖真实模型下载：通过伪造 fastembed 模块验证 builtin 分支被正确触发，
以及非 builtin 分支保持原有 HTTP 行为。
"""

import sys
import types

import pytest

from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig
from app.models.clients.rerank_client import (
    RerankClient,
    RerankConfig,
    RerankItem,
)


def _install_fake_fastembed(monkeypatch) -> dict[str, list[str]]:
    """注入一个伪造的 fastembed 模块，记录调用参数。"""
    embed_calls: dict[str, list[str]] = {"documents": []}

    class FakeTextEmbedding:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def embed(self, documents: list[str]):
            embed_calls["documents"] = list(documents)
            for _ in documents:
                yield [0.0, 0.1, 0.2]

    class FakeTextCrossEncoder:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def rerank(self, query: str, documents: list[str]):
            for i in range(len(documents)):
                yield float(len(documents) - i)

    fake_module = types.ModuleType("fastembed")
    fake_module.TextEmbedding = FakeTextEmbedding  # type: ignore[attr-defined]

    rerank_module = types.ModuleType("fastembed.rerank.cross_encoder")
    rerank_module.TextCrossEncoder = FakeTextCrossEncoder  # type: ignore[attr-defined]

    cross_encoder_pkg = types.ModuleType("fastembed.rerank")
    cross_encoder_pkg.cross_encoder = rerank_module  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "fastembed", fake_module)
    monkeypatch.setitem(sys.modules, "fastembed.rerank", cross_encoder_pkg)
    monkeypatch.setitem(sys.modules, "fastembed.rerank.cross_encoder", rerank_module)
    return embed_calls


@pytest.mark.asyncio
async def test_embedding_client_builtin_uses_fastembed(monkeypatch):
    embed_calls = _install_fake_fastembed(monkeypatch)

    client = EmbeddingClient(
        EmbeddingConfig(
            provider_type="builtin",
            base_url="builtin://local",
            api_key="",
            model_id="BAAI/bge-small-zh-v1.5",
            dimensions=512,
        )
    )

    response = await client.embed(["hello", "world"])
    assert embed_calls["documents"] == ["hello", "world"]
    assert len(response.embeddings) == 2
    assert response.embeddings[0] == [0.0, 0.1, 0.2]

    single = await client.embed_single("query")
    assert single == [0.0, 0.1, 0.2]


@pytest.mark.asyncio
async def test_rerank_client_builtin_uses_fastembed(monkeypatch):
    _install_fake_fastembed(monkeypatch)

    client = RerankClient(
        RerankConfig(
            provider_type="builtin",
            base_url="builtin://local",
            api_key="",
            model_id="Xenova/ms-marco-MiniLM-L-6-v2",
        )
    )

    response = await client.rerank("query", ["doc1", "doc2", "doc3"], top_n=2)
    assert len(response.results) == 2
    assert all(isinstance(item, RerankItem) for item in response.results)
    scores = [item.relevance_score for item in response.results]
    assert scores == sorted(scores, reverse=True)


def test_rerank_client_accepts_builtin_provider():
    client = RerankClient(
        RerankConfig(
            provider_type="builtin",
            base_url="builtin://local",
            api_key="",
            model_id="Xenova/ms-marco-MiniLM-L-6-v2",
        )
    )
    assert client.config.provider_type == "builtin"


def test_embedding_client_forces_openai_compatible_for_non_builtin_provider():
    client = EmbeddingClient(
        EmbeddingConfig(
            provider_type="cohere",
            base_url="https://api.cohere.com/v2",
            api_key="test-key",
            model_id="embed-v4.0",
            use_openai_compatible=True,
        )
    )

    from langchain_openai import OpenAIEmbeddings

    assert isinstance(client._get_embeddings(), OpenAIEmbeddings)


def test_rerank_client_forces_openai_compatible_for_non_builtin_provider():
    client = RerankClient(
        RerankConfig(
            provider_type="upstage",
            base_url="https://api.upstage.ai/v1/solar",
            api_key="test-key",
            model_id="solar-rerank",
            use_openai_compatible=True,
        )
    )

    assert client.runtime_provider_type == "openai-compatible"
