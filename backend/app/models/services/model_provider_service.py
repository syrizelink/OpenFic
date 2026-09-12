# -*- coding: utf-8 -*-
"""
Model Provider Service - lapisan logika bisnis penyedia layanan model.

Service berperan sebagai Executor, satu-satunya tempat pemanggilan dilakukan,
bertanggung jawab atas retry, circuit breaker, fallback, dan observasi.
"""

import json
from collections.abc import Mapping
from typing import Any

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.core.errors import NotFoundError
from app.models.catalog import CatalogMatch, ModelProviderCatalogService
from app.models.entities.model_provider import ModelProvider
from app.models.registry import AdapterRegistry
from app.models.repos import model_provider_repo


CUSTOM_PROVIDER_TYPES = frozenset(
    {
        "openai-compatible",
        "openai-compatible-responses",
        "anthropic-compatible",
        "gemini-compatible",
    }
)


class ModelProviderService:
    """Service penyedia layanan model (Executor), menjalankan pemanggilan dan observasi."""

    def __init__(
        self,
        encryption_service: EncryptionService,
        catalog_service: ModelProviderCatalogService | None = None,
    ):
        """
        Menginisialisasi service.

        Args:
            encryption_service: instance layanan enkripsi.
        """
        self.encryption_service = encryption_service
        self.catalog_service = catalog_service or ModelProviderCatalogService()

    # ========================
    # Operasi CRUD
    # ========================

    async def get_all_providers(self, session: AsyncSession) -> list[ModelProvider]:
        """
        Mengambil semua penyedia.

        Args:
            session: session basis data.

        Returns:
            Daftar penyedia.
        """
        return await model_provider_repo.get_all(session)

    async def get_catalog_match(self, provider: ModelProvider) -> CatalogMatch | None:
        return await self.catalog_service.match_saved_provider(
            provider.provider_type, provider.url
        )

    async def get_supported_task_types(
        self,
        provider: ModelProvider,
        catalog_match: CatalogMatch | None = None,
    ) -> list[str]:
        if provider.is_builtin:
            return ["embedding", "rerank"]
        if provider.provider_type == "gemini-compatible":
            return ["llm"]
        if catalog_match is None:
            catalog_match = await self.get_catalog_match(provider)
        return self.catalog_service.get_supported_task_types(
            provider.provider_type,
            catalog_match,
        )

    async def get_effective_icon_path(
        self,
        provider: ModelProvider,
        catalog_match: CatalogMatch | None = None,
    ) -> str | None:
        if catalog_match is None:
            catalog_match = await self.get_catalog_match(provider)
        return catalog_match.icon_path if catalog_match else None

    def get_decrypted_custom_headers(self, provider: ModelProvider) -> dict[str, str]:
        """Mengambil header permintaan penyedia kustom, nilainya tidak diekspos ke respons API."""
        if provider.provider_type not in CUSTOM_PROVIDER_TYPES:
            return {}

        encrypted_headers = provider.custom_headers_encrypted
        if not encrypted_headers:
            return {}

        try:
            payload = json.loads(self.encryption_service.decrypt(encrypted_headers))
        except Exception:
            logger.warning("Failed to decrypt custom headers for provider {}", provider.id)
            return {}

        if not isinstance(payload, dict):
            return {}
        return {
            key: value
            for key, value in payload.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def get_custom_header_names(self, provider: ModelProvider) -> list[str]:
        """Mengambil nama header permintaan kustom yang telah dikonfigurasi."""
        return list(self.get_decrypted_custom_headers(provider))

    @staticmethod
    def _normalize_custom_headers(
        provider_type: str,
        entries: list[dict[str, str]] | None,
        existing_headers: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Membersihkan input header permintaan, dan mempertahankan nilai lama yang tidak diisi ulang saat pembaruan."""
        existing = dict(existing_headers or {})
        normalized: dict[str, str] = {}

        for entry in entries or []:
            key = entry.get("key", "").strip()
            value = entry.get("value", "")
            if not isinstance(value, str):
                raise ValueError("Nilai header permintaan kustom harus berupa string")
            if not key and not value:
                continue
            if "\r" in key or "\n" in key or "\r" in value or "\n" in value:
                raise ValueError("Header permintaan kustom tidak boleh memuat karakter baris baru")
            if not key:
                continue

            existing_key = next(
                (name for name in existing if name.casefold() == key.casefold()),
                None,
            )
            if not value and existing_key is not None:
                normalized[key] = existing[existing_key]
            elif value:
                normalized[key] = value

        if provider_type not in CUSTOM_PROVIDER_TYPES and normalized:
            raise ValueError("Header permintaan kustom hanya didukung untuk penyedia bertipe kustom")
        return normalized

    async def get_provider_by_id(
        self, session: AsyncSession, provider_id: str
    ) -> ModelProvider:
        """
        Mengambil penyedia berdasarkan ID.

        Args:
            session: session basis data.
            provider_id: ID penyedia.

        Returns:
            Instance penyedia.

        Raises:
            NotFoundError: jika penyedia tidak ditemukan.
        """
        provider = await model_provider_repo.get_by_id(session, provider_id)
        if not provider:
            raise NotFoundError(f"Provider with id {provider_id} not found")
        return provider

    async def create_provider(
        self,
        session: AsyncSession,
        name: str,
        url: str,
        api_key: str,
        provider_type: str,
        custom_headers: list[dict[str, str]] | None = None,
    ) -> ModelProvider:
        """
        Membuat penyedia.

        Args:
            session: session basis data.
            name: nama penyedia.
            url: URL layanan.
            api_key: API Key (teks polos).
            provider_type: jenis penyedia.
            custom_headers: header permintaan kustom.

        Returns:
            Instance penyedia yang dibuat.
        """
        url = await self._resolve_provider_url(provider_type, url)

        # Enkripsi API Key
        encrypted_key = self.encryption_service.encrypt(api_key) if api_key else ""
        normalized_headers = self._normalize_custom_headers(provider_type, custom_headers)
        encrypted_headers = (
            self.encryption_service.encrypt(json.dumps(normalized_headers, ensure_ascii=False))
            if normalized_headers
            else ""
        )

        provider = await model_provider_repo.create(
            session=session,
            name=name,
            url=url,
            api_key_encrypted=encrypted_key,
            provider_type=provider_type,
            custom_headers_encrypted=encrypted_headers,
        )
        await session.commit()
        return provider

    async def _resolve_provider_url(self, provider_type: str, url: str) -> str:
        if provider_type in {
            "openai-compatible",
            "openai-compatible-responses",
            "anthropic-compatible",
            "gemini-compatible",
        }:
            return url

        try:
            catalog_provider = await self.catalog_service.get_provider(provider_type)
        except KeyError:
            return url

        return catalog_provider.api or url

    async def update_provider(
        self,
        session: AsyncSession,
        provider_id: str,
        name: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
        provider_type: str | None = None,
        custom_headers: list[dict[str, str]] | None = None,
    ) -> ModelProvider:
        """
        Memperbarui penyedia.

        Args:
            session: session basis data.
            provider_id: ID penyedia.
            name: nama penyedia.
            url: URL layanan.
            api_key: API Key (teks polos), jika diberikan maka dienkripsi ulang.
            provider_type: jenis penyedia.
            custom_headers: header permintaan kustom.

        Returns:
            Instance penyedia setelah diperbarui.

        Raises:
            NotFoundError: jika penyedia tidak ditemukan.
        """
        existing = await model_provider_repo.get_by_id(session, provider_id)
        if existing is None:
            raise NotFoundError(f"Provider with id {provider_id} not found")
        if existing.is_builtin:
            raise ValueError("Penyedia bawaan tidak boleh diedit")

        # Enkripsi API Key (jika diberikan)
        encrypted_key = None
        if api_key is not None:
            encrypted_key = self.encryption_service.encrypt(api_key) if api_key else ""

        effective_provider_type = provider_type or existing.provider_type
        encrypted_headers = None
        if custom_headers is not None:
            normalized_headers = self._normalize_custom_headers(
                effective_provider_type,
                custom_headers,
                self.get_decrypted_custom_headers(existing),
            )
            encrypted_headers = (
                self.encryption_service.encrypt(
                    json.dumps(normalized_headers, ensure_ascii=False)
                )
                if normalized_headers
                else ""
            )
        elif effective_provider_type not in CUSTOM_PROVIDER_TYPES:
            encrypted_headers = ""

        provider = await model_provider_repo.update(
            session=session,
            provider_id=provider_id,
            name=name,
            url=url,
            api_key_encrypted=encrypted_key,
            custom_headers_encrypted=encrypted_headers,
            provider_type=provider_type,
        )

        if not provider:
            raise NotFoundError(f"Provider with id {provider_id} not found")

        await session.commit()
        return provider

    async def delete_provider(self, session: AsyncSession, provider_id: str) -> None:
        """
        Menghapus penyedia.

        Args:
            session: session basis data.
            provider_id: ID penyedia.

        Raises:
            NotFoundError: jika penyedia tidak ditemukan.
            ValueError: jika penyedia adalah penyedia bawaan, tidak boleh dihapus.
        """
        provider = await model_provider_repo.get_by_id(session, provider_id)
        if provider is None:
            raise NotFoundError(f"Provider with id {provider_id} not found")
        if provider.is_builtin:
            raise ValueError("Penyedia bawaan tidak boleh dihapus")
        success = await model_provider_repo.delete_by_id(session, provider_id)
        if not success:
            raise NotFoundError(f"Provider with id {provider_id} not found")
        await session.commit()

    # ========================
    # Operasi API Key
    # ========================

    def get_decrypted_api_key(self, provider: ModelProvider) -> str | None:
        """
        Mengambil API Key yang telah didekripsi.

        Args:
            provider: instance penyedia.

        Returns:
            API Key setelah didekripsi, atau None jika field terenkripsi kosong
            atau dekripsi gagal.
        """
        if not provider.api_key_encrypted or provider.api_key_encrypted.strip() == "":
            return None

        try:
            return self.encryption_service.decrypt(provider.api_key_encrypted)
        except Exception as e:
            logger.warning(f"Failed to decrypt API key for provider {provider.id}: {e}")
            return None

    # ========================
    # Pengambilan daftar model (titik eksekusi Executor)
    # ========================

    async def validate_and_get_models(
        self,
        provider_type: str,
        url: str,
        api_key: str,
        custom_headers: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        """
        Memvalidasi koneksi penyedia dan mengambil daftar model.

        Args:
            provider_type: jenis penyedia.
            url: URL layanan.
            api_key: API Key (teks polos).
            custom_headers: header permintaan kustom.

        Returns:
            Daftar model, setiap model berformat
            {"id": "model-id", "name": "Model Name"}.

        Raises:
            Exception: jika validasi koneksi gagal.
        """
        url = await self._resolve_provider_url(provider_type, url)

        # Ambil model menggunakan Adapter terpadu
        runtime_provider_type = (
            "anthropic-compatible"
            if provider_type == "anthropic-compatible"
            else "openai-compatible-responses"
            if provider_type == "openai-compatible-responses"
            else "gemini-compatible"
            if provider_type == "gemini-compatible"
            else "openai-compatible"
        )
        adapter = AdapterRegistry.get_adapter(runtime_provider_type)
        request_headers = self._normalize_custom_headers(provider_type, custom_headers)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Default mengambil daftar model LLM (untuk validasi koneksi)
                if request_headers:
                    return await adapter.get_llm_models(
                        client,
                        url,
                        api_key,
                        headers=request_headers,
                    )
                return await adapter.get_llm_models(client, url, api_key)
        except Exception as e:
            logger.error(f"Validasi koneksi penyedia gagal: {e}")
            raise

    async def get_available_models(
        self, provider: ModelProvider, task_type: str
    ) -> list[dict[str, str]]:
        """
        Mengambil daftar model tersedia untuk provider dan task_type tertentu
        (titik eksekusi Executor).

        Args:
            provider: instance penyedia.
            task_type: jenis tugas (llm, embedding, atau rerank).

        Returns:
            Daftar model.

        Raises:
            ValueError: jika kombinasi provider dan task_type tidak didukung.
            Exception: jika permintaan gagal.
        """
        if provider.is_builtin:
            return self._builtin_available_models(task_type)

        logger.info(
            f"Fetching available models for provider={provider.provider_type}, task_type={task_type}"
        )

        # Periksa apakah didukung
        runtime_provider_type = (
            "anthropic-compatible"
            if provider.provider_type == "anthropic-compatible"
            else "openai-compatible-responses"
            if provider.provider_type == "openai-compatible-responses"
            else "gemini-compatible"
            if provider.provider_type == "gemini-compatible"
            else "openai-compatible"
        )
        if not AdapterRegistry.is_supported(runtime_provider_type, task_type):
            raise ValueError(
                f"Provider '{provider.provider_type}' does not support task_type '{task_type}'"
            )

        # Ambil Adapter
        adapter = AdapterRegistry.get_adapter(runtime_provider_type)

        # Dekripsi API Key
        api_key = self.encryption_service.decrypt(provider.api_key_encrypted)
        request_headers = self.get_decrypted_custom_headers(provider)

        # Buat klien HTTP dan jalankan permintaan
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Rutekan ke metode yang sesuai berdasarkan task_type
                if task_type == "llm":
                    if request_headers:
                        models = await adapter.get_llm_models(
                            client,
                            provider.url,
                            api_key,
                            headers=request_headers,
                        )
                    else:
                        models = await adapter.get_llm_models(client, provider.url, api_key)
                elif task_type == "rerank":
                    if request_headers:
                        models = await adapter.get_rerank_models(
                            client,
                            provider.url,
                            api_key,
                            headers=request_headers,
                        )
                    else:
                        models = await adapter.get_rerank_models(client, provider.url, api_key)
                else:
                    if request_headers:
                        models = await adapter.get_embedding_models(
                            client,
                            provider.url,
                            api_key,
                            headers=request_headers,
                        )
                    else:
                        models = await adapter.get_embedding_models(client, provider.url, api_key)

                logger.info(
                    f"Successfully fetched {len(models)} models for provider={provider.provider_type}, task_type={task_type}"
                )
                return models

        except Exception as e:
            logger.error(
                "Failed to fetch models for provider={}, task_type={}: {}",
                provider.provider_type,
                task_type,
                str(e),
                exc_info=True,
            )
            raise

    async def enrich_models_with_catalog_metadata(
        self,
        provider: ModelProvider,
        task_type: str,
        models: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Menyelaraskan model dari remote dengan metadata catalog berdasarkan model id."""

        enriched_models: list[dict[str, Any]] = [
            {
                "id": model["id"],
                "name": model["name"],
                "task_type": task_type,
                "metadata": None,
            }
            for model in models
        ]

        if not models:
            return enriched_models

        catalog_match = await self.get_catalog_match(provider)
        if catalog_match is None:
            return enriched_models

        try:
            catalog_models = await self.catalog_service.get_provider_models(
                catalog_match.catalog_provider_type,
                task_type,
            )
        except KeyError:
            return enriched_models

        catalog_models_by_id = {
            model.model_id: model for model in catalog_models.models
        }

        for model in enriched_models:
            matched_model = catalog_models_by_id.get(model["id"])
            if matched_model is None:
                continue

            model["name"] = matched_model.display_name
            model["task_type"] = matched_model.task_type
            model["metadata"] = matched_model.metadata

        return self.catalog_service._sort_model_dicts_by_release_date(enriched_models)

    @staticmethod
    def _builtin_available_models(task_type: str) -> list[dict[str, str]]:
        """Daftar model tetap untuk penyedia bawaan."""
        from app.models.builtin import BUILTIN_MODELS

        return [
            {"id": spec.model_id, "name": spec.name}
            for spec in BUILTIN_MODELS
            if spec.task_type == task_type
        ]
