# -*- coding: utf-8 -*-
"""
Clients Module - 模型调用客户端模块。

包含：
- ClientFactory: HTTP客户端工厂
- LLMClient: LLM模型调用（流式/非流式）
- EmbeddingClient: Embedding模型调用
- RerankClient: Rerank 模型调用
"""

from app.models.clients.client_factory import ClientFactory
from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig, EmbeddingResponse
from app.models.clients.llm_client import LLMClient, LLMConfig, LLMResponse, LLMStreamChunk
from app.models.clients.rerank_client import (
    RerankClient,
    RerankConfig,
    RerankItem,
    RerankResponse,
)

__all__ = [
    "ClientFactory",
    "LLMClient",
    "LLMConfig",
    "LLMResponse",
    "LLMStreamChunk",
    "EmbeddingClient",
    "EmbeddingConfig",
    "EmbeddingResponse",
    "RerankClient",
    "RerankConfig",
    "RerankItem",
    "RerankResponse",
]
