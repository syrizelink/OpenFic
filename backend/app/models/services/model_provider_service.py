# -*- coding: utf-8 -*-
"""
Model Provider Service - 模型服务提供商业务逻辑层。

Service作为Executor，是唯一发起调用的地方，负责处理重试、熔断、fallback和观测。
"""

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


class ModelProviderService:
    """模型服务提供商Service（Executor），负责执行调用和观测。"""

    def __init__(
        self,
        encryption_service: EncryptionService,
        catalog_service: ModelProviderCatalogService | None = None,
    ):
        """
        初始化服务。

        Args:
            encryption_service: 加密服务实例。
        """
        self.encryption_service = encryption_service
        self.catalog_service = catalog_service or ModelProviderCatalogService()

    # ========================
    # CRUD 操作
    # ========================

    async def get_all_providers(self, session: AsyncSession) -> list[ModelProvider]:
        """
        获取所有提供商。

        Args:
            session: 数据库 session。

        Returns:
            提供商列表。
        """
        return await model_provider_repo.get_all(session)

    async def get_catalog_match(self, provider: ModelProvider) -> CatalogMatch | None:
        return await self.catalog_service.match_saved_provider(
            provider.provider_type, provider.url
        )

    async def get_supported_task_types(self, provider: ModelProvider) -> list[str]:
        if provider.is_builtin:
            return ["embedding", "rerank"]
        catalog_match = await self.get_catalog_match(provider)
        return self.catalog_service.get_supported_task_types(
            provider.provider_type,
            catalog_match,
        )

    async def get_effective_icon_path(self, provider: ModelProvider) -> str | None:
        catalog_match = await self.get_catalog_match(provider)
        return catalog_match.icon_path if catalog_match else None

    async def get_provider_by_id(
        self, session: AsyncSession, provider_id: str
    ) -> ModelProvider:
        """
        根据ID获取提供商。

        Args:
            session: 数据库session。
            provider_id: 提供商ID。

        Returns:
            提供商实例。

        Raises:
            NotFoundError: 如果提供商不存在。
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
    ) -> ModelProvider:
        """
        创建提供商。

        Args:
            session: 数据库 session。
            name: 提供商名称。
            url: 服务 URL。
            api_key: API Key（明文）。
            provider_type: 提供商类型。

        Returns:
            创建的提供商实例。
        """
        url = await self._resolve_provider_url(provider_type, url)

        # 加密 API Key
        encrypted_key = self.encryption_service.encrypt(api_key) if api_key else ""

        provider = await model_provider_repo.create(
            session=session,
            name=name,
            url=url,
            api_key_encrypted=encrypted_key,
            provider_type=provider_type,
        )
        await session.commit()
        return provider

    async def _resolve_provider_url(self, provider_type: str, url: str) -> str:
        if provider_type == "openai-compatible":
            return url

        try:
            catalog_provider = await self.catalog_service.get_provider(provider_type)
        except KeyError:
            return url

        return catalog_provider.default_url or catalog_provider.api or url

    async def update_provider(
        self,
        session: AsyncSession,
        provider_id: str,
        name: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
        provider_type: str | None = None,
    ) -> ModelProvider:
        """
        更新提供商。

        Args:
            session: 数据库 session。
            provider_id: 提供商 ID。
            name: 提供商名称。
            url: 服务 URL。
            api_key: API Key（明文），如果提供则重新加密。
            provider_type: 提供商类型。

        Returns:
            更新后的提供商实例。

        Raises:
            NotFoundError: 如果提供商不存在。
        """
        # 加密 API Key（如果提供）
        encrypted_key = None
        if api_key is not None:
            encrypted_key = self.encryption_service.encrypt(api_key) if api_key else ""

        existing = await model_provider_repo.get_by_id(session, provider_id)
        if existing is None:
            raise NotFoundError(f"Provider with id {provider_id} not found")
        if existing.is_builtin:
            raise ValueError("内置提供商不允许编辑")

        provider = await model_provider_repo.update(
            session=session,
            provider_id=provider_id,
            name=name,
            url=url,
            api_key_encrypted=encrypted_key,
            provider_type=provider_type,
        )

        if not provider:
            raise NotFoundError(f"Provider with id {provider_id} not found")

        await session.commit()
        return provider

    async def delete_provider(self, session: AsyncSession, provider_id: str) -> None:
        """
        删除提供商。

        Args:
            session: 数据库 session。
            provider_id: 提供商 ID。

        Raises:
            NotFoundError: 如果提供商不存在。
            ValueError: 如果提供商为内置提供商，不允许删除。
        """
        provider = await model_provider_repo.get_by_id(session, provider_id)
        if provider is None:
            raise NotFoundError(f"Provider with id {provider_id} not found")
        if provider.is_builtin:
            raise ValueError("内置提供商不允许删除")
        success = await model_provider_repo.delete_by_id(session, provider_id)
        if not success:
            raise NotFoundError(f"Provider with id {provider_id} not found")
        await session.commit()

    # ========================
    # API Key 操作
    # ========================

    def get_decrypted_api_key(self, provider: ModelProvider) -> str | None:
        """
        获取解密后的 API Key。

        Args:
            provider: 提供商实例。

        Returns:
            解密后的 API Key，如果加密字段为空或解密失败返回 None。
        """
        if not provider.api_key_encrypted or provider.api_key_encrypted.strip() == "":
            return None

        try:
            return self.encryption_service.decrypt(provider.api_key_encrypted)
        except Exception as e:
            logger.warning(f"Failed to decrypt API key for provider {provider.id}: {e}")
            return None

    # ========================
    # 模型列表获取（Executor执行点）
    # ========================

    async def validate_and_get_models(
        self, provider_type: str, url: str, api_key: str
    ) -> list[dict[str, str]]:
        """
        验证提供商连接并获取模型列表。

        Args:
            provider_type: 提供商类型。
            url: 服务 URL。
            api_key: API Key（明文）。

        Returns:
            模型列表，每个模型为 {"id": "model-id", "name": "Model Name"} 格式。

        Raises:
            Exception: 如果连接验证失败。
        """
        url = await self._resolve_provider_url(provider_type, url)

        # 使用统一的Adapter获取模型
        adapter = AdapterRegistry.get_adapter("openai-compatible")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 默认获取LLM模型列表（用于连接验证）
                return await adapter.get_llm_models(client, url, api_key)
        except Exception as e:
            logger.error(f"验证提供商连接失败: {e}")
            raise

    async def get_available_models(
        self, provider: ModelProvider, task_type: str
    ) -> list[dict[str, str]]:
        """
        获取指定provider和task_type的可用模型列表（Executor执行点）。

        Args:
            provider: 提供商实例。
            task_type: 任务类型（llm、embedding 或 rerank）。

        Returns:
            模型列表。

        Raises:
            ValueError: 如果不支持该provider和task_type组合。
            Exception: 如果请求失败。
        """
        if provider.is_builtin:
            return self._builtin_available_models(task_type)

        logger.info(
            f"Fetching available models for provider={provider.provider_type}, task_type={task_type}"
        )

        # 检查是否支持
        runtime_provider_type = "openai-compatible"
        if not AdapterRegistry.is_supported(runtime_provider_type, task_type):
            raise ValueError(
                f"Provider '{provider.provider_type}' does not support task_type '{task_type}'"
            )

        # 获取Adapter
        adapter = AdapterRegistry.get_adapter(runtime_provider_type)

        # 解密API Key
        api_key = self.encryption_service.decrypt(provider.api_key_encrypted)

        # 创建HTTP客户端并执行请求
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 根据task_type路由到对应方法
                if task_type == "llm":
                    models = await adapter.get_llm_models(client, provider.url, api_key)
                elif task_type == "rerank":
                    models = await adapter.get_rerank_models(
                        client, provider.url, api_key
                    )
                else:
                    models = await adapter.get_embedding_models(
                        client, provider.url, api_key
                    )

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
        """按 model id 将远端返回模型与 catalog 元数据对齐。"""

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
        """内置提供商的固定模型列表。"""
        from app.models.builtin import BUILTIN_MODELS

        return [
            {"id": spec.model_id, "name": spec.name}
            for spec in BUILTIN_MODELS
            if spec.task_type == task_type
        ]
