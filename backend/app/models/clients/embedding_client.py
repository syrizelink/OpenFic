# -*- coding: utf-8 -*-
"""
Embedding Client - klien pemanggilan model embedding.

Menyediakan antarmuka pembuatan vektor embedding teks menggunakan komponen LangChain.
"""

from dataclasses import dataclass
from typing import Any, Protocol, cast

from langchain_core.embeddings import Embeddings
from loguru import logger
from pydantic import SecretStr

from app.models.helpers.openrouter_attribution import get_openrouter_attribution_headers


@dataclass
class EmbeddingConfig:
    """Konfigurasi pemanggilan embedding."""

    provider_type: str
    base_url: str
    api_key: str
    model_id: str
    custom_headers: dict[str, str] | None = None
    dimensions: int | None = None
    batch_size: int = 50
    use_openai_compatible: bool = True


@dataclass
class EmbeddingResponse:
    """Respons embedding."""

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
    """Klien pemanggilan model embedding, menggunakan komponen LangChain."""

    def __init__(self, config: EmbeddingConfig):
        """
        Menginisialisasi klien embedding.

        Args:
            config: konfigurasi embedding.
        """
        self.config = config
        self._embeddings: Embeddings | None = None

    def _get_embeddings(self) -> Embeddings:
        """Mengambil atau membuat instance Embeddings LangChain."""
        if self._embeddings is not None:
            return self._embeddings

        config = self.config
        provider = (
            "builtin"
            if config.provider_type == "builtin"
            else "openai-compatible"
            if config.use_openai_compatible or config.provider_type == "ollama"
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
            # Format kompatibel OpenAI (openai, openrouter, openai-compatible, dll)
            from langchain_openai import OpenAIEmbeddings

            openai_kwargs: dict[str, Any] = {
                "model": config.model_id,
                "api_key": config.api_key,
                "base_url": config.base_url,
                # Endpoint non-resmi OpenAI umumnya tidak mendukung input array token
                # dan encoding base64: kirim teks asli dan gunakan format float untuk
                # menghindari respons kosong/dekode gagal.
                "check_embedding_ctx_length": False,
                "model_kwargs": {"encoding_format": "float"},
            }
            if config.provider_type == "openrouter":
                openai_kwargs["default_headers"] = {
                    **get_openrouter_attribution_headers(),
                    **(config.custom_headers or {}),
                }
            elif config.custom_headers:
                openai_kwargs["default_headers"] = config.custom_headers
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
            logger.error(f"Pemanggilan embedding gagal: {e}")
            raise

    async def embed_single(self, text: str) -> list[float]:
        """
        Membuat vektor embedding untuk satu teks.

        Args:
            text: teks yang akan di-embed.

        Returns:
            Vektor embedding.
        """
        try:
            embeddings_model = self._get_embeddings()
            return await embeddings_model.aembed_query(text)
        except Exception as e:
            logger.error(f"Pemanggilan embedding gagal: {e}")
            raise
