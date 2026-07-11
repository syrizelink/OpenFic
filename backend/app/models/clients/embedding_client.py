# -*- coding: utf-8 -*-
"""
Embedding Client - Embedding模型调用客户端。

使用LangChain组件提供文本嵌入向量生成接口。
"""

from dataclasses import dataclass
from typing import Any, Protocol, cast

from langchain_core.embeddings import Embeddings
from loguru import logger
from pydantic import SecretStr


@dataclass
class EmbeddingConfig:
    """Embedding调用配置。"""

    provider_type: str
    base_url: str
    api_key: str
    model_id: str
    dimensions: int | None = None
    batch_size: int = 50
    use_openai_compatible: bool = True


@dataclass
class EmbeddingResponse:
    """Embedding响应。"""

    embeddings: list[list[float]]
    model: str | None = None
    usage: dict[str, Any] | None = None


class EmbeddingClientConfigLike(Protocol):
    model_id: str
    dimensions: int | None


class EmbeddingResponseLike(Protocol):
    embeddings: list[list[float]]


class EmbeddingClientLike(Protocol):
    config: EmbeddingClientConfigLike

    async def embed(self, texts: list[str]) -> EmbeddingResponseLike: ...

    async def embed_single(self, text: str) -> list[float]: ...


class EmbeddingClient:
    """Embedding模型调用客户端，使用LangChain组件。"""

    def __init__(self, config: EmbeddingConfig):
        """
        初始化Embedding客户端。

        Args:
            config: Embedding配置。
        """
        self.config = config
        self._embeddings: Embeddings | None = None

    def _get_embeddings(self) -> Embeddings:
        """获取或创建LangChain Embeddings实例。"""
        if self._embeddings is not None:
            return self._embeddings

        config = self.config
        provider = (
            "builtin"
            if config.provider_type == "builtin"
            else "openai-compatible"
            if config.use_openai_compatible
            else config.provider_type
        )

        if provider == "builtin":
            from app.models.clients.fastembed_embeddings import FastEmbedEmbeddings

            self._embeddings = FastEmbedEmbeddings(model_name=config.model_id)
            return self._embeddings

        if provider == "google-genai":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            self._embeddings = GoogleGenerativeAIEmbeddings(
                model=config.model_id,
                api_key=SecretStr(config.api_key),
                base_url=config.base_url or None,
            )
        elif provider == "mistral":
            from langchain_mistralai import MistralAIEmbeddings

            self._embeddings = MistralAIEmbeddings(
                model=config.model_id,
                api_key=cast(Any, config.api_key),
            )
        elif provider == "ollama":
            from langchain_ollama import OllamaEmbeddings

            self._embeddings = OllamaEmbeddings(
                model=config.model_id,
                base_url=config.base_url,
                dimensions=config.dimensions,
            )
        elif provider == "cohere":
            from langchain_cohere import CohereEmbeddings

            cohere_kwargs: dict[str, Any] = {
                "model": config.model_id,
                "cohere_api_key": config.api_key,
                "base_url": config.base_url or None,
                "client": None,
                "async_client": None,
            }
            self._embeddings = CohereEmbeddings(**cohere_kwargs)
        elif provider == "nvidia-ai-endpoints":
            from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

            self._embeddings = NVIDIAEmbeddings(
                model=config.model_id,
                api_key=config.api_key,
                base_url=config.base_url or None,
                dimensions=config.dimensions,
            )
        else:
            # OpenAI兼容格式（openai, openrouter, openai-compatible等）
            from langchain_openai import OpenAIEmbeddings

            openai_kwargs: dict[str, Any] = {
                "model": config.model_id,
                "api_key": config.api_key,
                "base_url": config.base_url,
                # 非OpenAI官方端点通常不支持token数组输入与base64编码：
                # 发送原始文本并使用float格式，避免空响应/解码失败。
                "check_embedding_ctx_length": False,
                "encoding_format": "float",
            }
            if config.dimensions is not None:
                openai_kwargs["dimensions"] = config.dimensions

            self._embeddings = OpenAIEmbeddings(**openai_kwargs)

        return self._embeddings

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        all_embeddings: list[list[float]] = []

        try:
            embeddings_model = self._get_embeddings()
            for i in range(0, len(texts), self.config.batch_size):
                batch = texts[i : i + self.config.batch_size]
                all_embeddings.extend(
                    await embeddings_model.aembed_documents(batch)
                )
            return EmbeddingResponse(
                embeddings=all_embeddings,
                model=self.config.model_id,
            )
        except Exception as e:
            logger.error(f"Embedding调用失败: {e}")
            raise

    async def embed_single(self, text: str) -> list[float]:
        """
        生成单个文本的嵌入向量。

        Args:
            text: 待嵌入的文本。

        Returns:
            嵌入向量。
        """
        try:
            embeddings_model = self._get_embeddings()
            return await embeddings_model.aembed_query(text)
        except Exception as e:
            logger.error(f"Embedding调用失败: {e}")
            raise
