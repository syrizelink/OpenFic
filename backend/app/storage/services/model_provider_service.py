# -*- coding: utf-8 -*-
"""
ModelProvider Service - 模型服务提供商业务逻辑层。
"""

import httpx
from cryptography.fernet import InvalidToken
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.core.errors import NotFoundError
from app.models.entities.model_provider import ModelProvider
from app.models.repos import model_provider_repo


class ModelProviderService:
    """模型服务提供商 Service。"""

    def __init__(self, encryption_service: EncryptionService):
        """
        初始化服务。

        Args:
            encryption_service: 加密服务实例。
        """
        self.encryption_service = encryption_service

    def get_decrypted_api_key(self, provider: ModelProvider) -> str:
        """
        获取解密后的 API Key。

        Args:
            provider: 提供商实例。

        Returns:
            解密后的 API Key。如果 API Key 为空或解密失败，返回空字符串。
        """
        # 检查字段是否存在且非空
        if not provider.api_key_encrypted or provider.api_key_encrypted.strip() == "":
            logger.debug(f"Provider {provider.id} has empty API key field")
            return ""
        
        try:
            decrypted = self.encryption_service.decrypt(provider.api_key_encrypted)
            # 如果解密后是空字符串，也视为无效
            if not decrypted or decrypted.strip() == "":
                logger.debug(f"Provider {provider.id} decrypted to empty string")
                return ""
            return decrypted
        except InvalidToken:
            # 加密数据无效（可能是密钥改变或数据损坏）
            logger.warning(
                f"Invalid encrypted API key for provider {provider.id}: "
                f"Token is invalid or encryption key has changed"
            )
            return ""
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e) if str(e) else repr(e)
            logger.warning(
                f"Failed to decrypt API key for provider {provider.id}: "
                f"{error_type}: {error_msg}"
            )
            return ""

    async def get_all_providers(self, session: AsyncSession) -> list[ModelProvider]:
        """
        获取所有提供商。

        Args:
            session: 数据库 session。

        Returns:
            提供商列表。
        """
        return await model_provider_repo.get_all(session)

    async def get_provider_by_id(
        self, session: AsyncSession, provider_id: str
    ) -> ModelProvider:
        """
        根据 ID 获取提供商。

        Args:
            session: 数据库 session。
            provider_id: 提供商 ID。

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
            name: 提供商名称/备注。
            url: 服务 URL。
            api_key: API Key（明文，将被加密）。
            provider_type: 提供商类型。

        Returns:
            创建的提供商实例。
        """
        # 加密 API Key（如果提供且非空）
        api_key_encrypted = ""
        if api_key and api_key.strip():
            try:
                api_key_encrypted = self.encryption_service.encrypt(api_key.strip())
            except Exception as e:
                logger.error("Failed to encrypt API key: {}", e)
                raise ValueError(f"无法加密 API Key: {str(e)}")

        provider = await model_provider_repo.create(
            session=session,
            name=name,
            url=url,
            api_key_encrypted=api_key_encrypted,
            provider_type=provider_type,
        )
        await session.commit()
        return provider

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
            name: 提供商名称/备注。
            url: 服务 URL。
            api_key: API Key（明文，将被加密）。
            provider_type: 提供商类型。

        Returns:
            更新后的提供商实例。

        Raises:
            NotFoundError: 如果提供商不存在。
        """
        # 如果提供了新的 API Key，加密它
        api_key_encrypted = None
        if api_key is not None and api_key:
            api_key_encrypted = self.encryption_service.encrypt(api_key)

        provider = await model_provider_repo.update(
            session=session,
            provider_id=provider_id,
            name=name,
            url=url,
            api_key_encrypted=api_key_encrypted,
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
        """
        success = await model_provider_repo.delete_by_id(session, provider_id)
        if not success:
            raise NotFoundError(f"Provider with id {provider_id} not found")
        await session.commit()

    def decrypt_api_key(self, provider: ModelProvider) -> str:
        """
        解密提供商的 API Key。

        Args:
            provider: 提供商实例。

        Returns:
            解密后的 API Key。
        """
        return self.encryption_service.decrypt(provider.api_key_encrypted)

    async def validate_and_get_models(
        self, provider_type: str, url: str, api_key: str
    ) -> list[dict[str, str]]:
        """
        验证提供商连接并获取模型列表。

        通过访问 URL/models 端点来验证连接并获取模型列表。
        对于不支持模型列表API的提供商（如Anthropic），返回预定义模型列表。

        Args:
            provider_type: 提供商类型。
            url: 服务 URL。
            api_key: API Key（明文）。

        Returns:
            模型列表，每个模型为 {"id": "model-id", "name": "Model Name"} 格式。
            如果获取失败或提供商不支持列表 API，返回空列表或预定义列表。

        Raises:
            Exception: 如果连接验证失败。
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 特殊处理：Anthropic 和 Google 可能不提供 models 端点
                if provider_type == "anthropic":
                    return await self._get_anthropic_models(client, url, api_key)
                elif provider_type == "google-genai":
                    return await self._get_google_genai_models(client, url, api_key)
                elif provider_type == "google-vertex":
                    return await self._get_google_vertex_models(client, url, api_key)
                elif provider_type == "openrouter":
                    return await self._get_openrouter_models(client, url, api_key)
                
                # 对于其他提供商，统一使用 /models 端点
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                
                base_url = url.rstrip("/")
                models_url = f"{base_url}/models"
                
                logger.info(f"Requesting models from: {models_url}")
                
                response = await client.get(models_url, headers=headers)
                response.raise_for_status()

                data = response.json()
                models = []
                
                # 处理返回的模型数据（支持多种格式）
                if isinstance(data, list):
                    # 直接返回数组格式
                    for model in data:
                        if isinstance(model, dict) and "id" in model:
                            models.append({
                                "id": model["id"],
                                "name": model.get("name", model["id"])
                            })
                elif isinstance(data, dict):
                    # 标准格式：{"data": [...]}
                    if "data" in data:
                        for model in data.get("data", []):
                            if isinstance(model, dict) and "id" in model:
                                models.append({
                                    "id": model["id"],
                                    "name": model.get("name", model["id"])
                                })
                    # 其他可能的格式
                    elif "models" in data:
                        for model in data.get("models", []):
                            if isinstance(model, dict) and "id" in model:
                                models.append({
                                    "id": model["id"],
                                    "name": model.get("name", model["id"])
                                })
                
                logger.info(f"Successfully retrieved {len(models)} models from {models_url}")
                return models
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            # 使用 loguru 的参数化日志记录，避免 error_msg 中的花括号被误认为格式化占位符
            logger.error("Failed to get models for {} at {}: {}", provider_type, url, error_msg)
            raise Exception(f"请求失败: HTTP {e.response.status_code} - {e.response.text[:200]}")
        except httpx.RequestError as e:
            error_msg = f"Request error: {str(e)}"
            logger.error("Failed to get models for {} at {}: {}", provider_type, url, error_msg)
            raise Exception(f"请求错误: {str(e)}")
        except Exception as e:
            error_msg = str(e)
            logger.error("Failed to get models for {} at {}: {}", provider_type, url, error_msg, exc_info=True)
            raise

    async def _get_openai_models(
        self, client: httpx.AsyncClient, url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取 OpenAI 模型列表。"""
        headers = {"Authorization": f"Bearer {api_key}"}
        base_url = url.rstrip("/")
        response = await client.get(f"{base_url}/models", headers=headers)
        response.raise_for_status()

        data = response.json()
        models = []
        for model in data.get("data", []):
            models.append({"id": model["id"], "name": model.get("id", model["id"])})
        return models

    async def _get_anthropic_models(
        self, client: httpx.AsyncClient, url: str, api_key: str
    ) -> list[dict[str, str]]:
        """
        获取 Anthropic 模型列表。

        注意：Anthropic API 不提供模型列表端点，返回预定义的常见模型。
        """
        # Anthropic 没有公开的模型列表 API，返回常见模型
        return [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
            {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
        ]

    async def _get_deepseek_models(
        self, client: httpx.AsyncClient, url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取 Deepseek 模型列表。"""
        headers = {"Authorization": f"Bearer {api_key}"}
        base_url = url.rstrip("/")
        response = await client.get(f"{base_url}/models", headers=headers)
        response.raise_for_status()

        data = response.json()
        models = []
        for model in data.get("data", []):
            models.append({"id": model["id"], "name": model["id"]})
        return models

    async def _get_google_genai_models(
        self, client: httpx.AsyncClient, url: str, api_key: str
    ) -> list[dict[str, str]]:
        """
        获取 Google Generative AI 模型列表。

        注意：返回预定义的常见模型。
        """
        # Google Generative AI 常见模型
        return [
            {"id": "gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash (Experimental)"},
            {"id": "gemini-exp-1206", "name": "Gemini Experimental 1206"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
            {"id": "gemini-1.0-pro", "name": "Gemini 1.0 Pro"},
        ]

    async def _get_google_vertex_models(
        self, client: httpx.AsyncClient, url: str, api_key: str
    ) -> list[dict[str, str]]:
        """
        获取 Google Vertex AI 模型列表。

        注意：返回预定义的常见模型。
        """
        # Google Vertex AI 常见模型
        return [
            {"id": "gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash (Experimental)"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
        ]

    async def _get_mistral_models(
        self, client: httpx.AsyncClient, url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取 Mistral AI 模型列表。"""
        headers = {"Authorization": f"Bearer {api_key}"}
        base_url = url.rstrip("/")
        response = await client.get(f"{base_url}/models", headers=headers)
        response.raise_for_status()

        data = response.json()
        models = []
        for model in data.get("data", []):
            models.append({"id": model["id"], "name": model.get("id", model["id"])})
        return models

    async def _get_openrouter_models(
        self, client: httpx.AsyncClient, url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取 OpenRouter 模型列表。"""
        headers = {"Authorization": f"Bearer {api_key}"}
        base_url = url.rstrip("/")
        response = await client.get(f"{base_url}/models", headers=headers)
        response.raise_for_status()

        data = response.json()
        models = []
        # OpenRouter 返回格式与 OpenAI 兼容，使用 "data" 字段
        for model in data.get("data", []):
            # OpenRouter 的模型数据可能包含更多信息，优先使用 name 字段
            model_id = model.get("id", "")
            model_name = model.get("name", model_id)
            models.append({"id": model_id, "name": model_name})
        return models

    async def _get_openai_compatible_models(
        self, client: httpx.AsyncClient, url: str, api_key: str
    ) -> list[dict[str, str]]:
        """获取 OpenAI 兼容服务的模型列表。"""
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            base_url = url.rstrip("/")
            response = await client.get(f"{base_url}/models", headers=headers)
            response.raise_for_status()

            data = response.json()
            models = []
            for model in data.get("data", []):
                models.append({"id": model["id"], "name": model.get("id", model["id"])})
            return models
        except Exception as e:
            logger.warning(f"Failed to get models from OpenAI-compatible API: {e}")
            # OpenAI 兼容服务可能不提供模型列表，返回空列表
            return []
