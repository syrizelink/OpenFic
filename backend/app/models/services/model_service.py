# -*- coding: utf-8 -*-
"""
Model Service - 模型业务逻辑层。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.entities.model import Model
from app.models.clients.model_params import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_FREQUENCY_PENALTY,
    DEFAULT_MIN_P,
    DEFAULT_PRESENCE_PENALTY,
    DEFAULT_REPETITION_PENALTY,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_A,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    with_default,
)
from app.models.repos import model_repo
from app.storage.repos import retrieval_index_repo


class ModelService:
    """模型 Service。"""

    async def get_all_models(self, session: AsyncSession) -> list[Model]:
        """
        获取所有模型。

        Args:
            session: 数据库 session。

        Returns:
            模型列表。
        """
        return await model_repo.get_all(session)

    async def get_models_by_provider(
        self, session: AsyncSession, provider_id: str, task_type: str | None = None
    ) -> list[Model]:
        """
        根据提供商 ID 获取模型列表，可选按task_type过滤。

        Args:
            session: 数据库 session。
            provider_id: 提供商 ID。
            task_type: 可选的任务类型过滤（llm、embedding 或 rerank）。

        Returns:
            模型列表。
        """
        models = await model_repo.get_by_provider_id(session, provider_id)
        if task_type:
            models = [m for m in models if m.task_type == task_type]
        return models

    async def get_model_by_id(self, session: AsyncSession, model_id: str) -> Model:
        """
        根据 ID 获取模型。

        Args:
            session: 数据库 session。
            model_id: 模型 ID。

        Returns:
            模型实例。

        Raises:
            NotFoundError: 如果模型不存在。
        """
        model = await model_repo.get_by_id(session, model_id)
        if not model:
            raise NotFoundError(f"Model with id {model_id} not found")
        return model

    async def create_model(
        self,
        session: AsyncSession,
        name: str,
        provider_id: str,
        model_id: str,
        task_type: str = "llm",
        remark: str = "",
        temperature: float | None = DEFAULT_TEMPERATURE,
        top_p: float | None = DEFAULT_TOP_P,
        top_k: int | None = DEFAULT_TOP_K,
        min_p: float | None = DEFAULT_MIN_P,
        top_a: float | None = DEFAULT_TOP_A,
        frequency_penalty: float | None = DEFAULT_FREQUENCY_PENALTY,
        presence_penalty: float | None = DEFAULT_PRESENCE_PENALTY,
        repetition_penalty: float | None = DEFAULT_REPETITION_PENALTY,
        max_tokens: int | None = None,
        context_length: int = DEFAULT_CONTEXT_LENGTH,
        dimensions: int | None = None,
    ) -> Model:
        """
        创建模型。

        Args:
            session: 数据库 session。
            name: 模型名称。
            provider_id: 关联的提供商 ID。
            model_id: 从提供商获取的模型 ID。
            task_type: 任务类型（llm、embedding 或 rerank）。
            remark: 备注。
            temperature: Temperature 参数（LLM）。
            top_p: Top P 参数（LLM）。
            top_k: Top K 参数（LLM）。
            min_p: Min P 参数（LLM）。
            top_a: Top A 参数（LLM）。
            frequency_penalty: Frequency Penalty 参数（LLM）。
            presence_penalty: Presence Penalty 参数（LLM）。
            repetition_penalty: Repetition Penalty 参数（LLM）。
            max_tokens: Max Tokens 参数（LLM）。
            dimensions: Embedding 维度（Embedding）。
        Returns:
            创建的模型实例。
        """
        if await model_repo.exists_by_name(session, name):
            raise ValueError("模型名称已存在")

        if task_type != "llm":
            temperature = None
            top_p = None
            top_k = None
            min_p = None
            top_a = None
            frequency_penalty = None
            presence_penalty = None
            repetition_penalty = None
        else:
            temperature = with_default(temperature, DEFAULT_TEMPERATURE)
            top_p = with_default(top_p, DEFAULT_TOP_P)
            top_k = with_default(top_k, DEFAULT_TOP_K)
            min_p = with_default(min_p, DEFAULT_MIN_P)
            top_a = with_default(top_a, DEFAULT_TOP_A)
            frequency_penalty = with_default(
                frequency_penalty, DEFAULT_FREQUENCY_PENALTY
            )
            presence_penalty = with_default(presence_penalty, DEFAULT_PRESENCE_PENALTY)
            repetition_penalty = with_default(
                repetition_penalty, DEFAULT_REPETITION_PENALTY
            )

        model = await model_repo.create(
            session=session,
            name=name,
            provider_id=provider_id,
            model_id=model_id,
            task_type=task_type,
            remark=remark,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            min_p=min_p,
            top_a=top_a,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            repetition_penalty=repetition_penalty,
            max_tokens=max_tokens,
            context_length=context_length,
            dimensions=dimensions,
        )
        await session.commit()
        return model

    async def update_model(
        self,
        session: AsyncSession,
        model_id: str,
        name: str | None = None,
        remark: str | None = None,
        provider_id: str | None = None,
        model_identifier: str | None = None,
        task_type: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        min_p: float | None = None,
        top_a: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        repetition_penalty: float | None = None,
        max_tokens: int | None = None,
        context_length: int | None = None,
        dimensions: int | None = None,
    ) -> Model:
        """
        更新模型。

        Args:
            session: 数据库 session。
            model_id: 模型 ID。
            name: 模型名称。
            remark: 备注。
            provider_id: 关联的提供商 ID。
            model_identifier: 从提供商获取的模型 ID。
            task_type: 任务类型。
            temperature: Temperature 参数。
            top_p: Top P 参数。
            top_k: Top K 参数。
            min_p: Min P 参数。
            top_a: Top A 参数。
            frequency_penalty: Frequency Penalty 参数。
            presence_penalty: Presence Penalty 参数。
            repetition_penalty: Repetition Penalty 参数。
            max_tokens: Max Tokens 参数。
            dimensions: Embedding 维度。
        Returns:
            更新后的模型实例。

        Raises:
            NotFoundError: 如果模型不存在。
        """
        existing = await self.get_model_by_id(session, model_id)
        if existing.is_builtin:
            raise ValueError("内置模型不允许编辑")
        if name is not None and await model_repo.exists_by_name(
            session, name, exclude_model_id=model_id
        ):
            raise ValueError("模型名称已存在")
        if await retrieval_index_repo.exists_by_embedding_model_ref_id(session, model_id):
            protected_changes = []
            if provider_id is not None and provider_id != existing.provider_id:
                protected_changes.append("provider_id")
            if model_identifier is not None and model_identifier != existing.model_id:
                protected_changes.append("model_id")
            if dimensions is not None and dimensions != existing.dimensions:
                protected_changes.append("dimensions")
            if protected_changes:
                raise ValueError(
                    "Embedding model is bound to retrieval indexes; cannot change "
                    + ", ".join(protected_changes)
                )

        model = await model_repo.update(
            session=session,
            model_id=model_id,
            name=name,
            remark=remark,
            provider_id=provider_id,
            model_identifier=model_identifier,
            task_type=task_type,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            min_p=min_p,
            top_a=top_a,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            repetition_penalty=repetition_penalty,
            max_tokens=max_tokens,
            context_length=context_length,
            dimensions=dimensions,
        )

        if not model:
            raise NotFoundError(f"Model with id {model_id} not found")

        await session.commit()
        return model

    async def delete_model(self, session: AsyncSession, model_id: str) -> None:
        """
        删除模型。

        Args:
            session: 数据库 session。
            model_id: 模型 ID。

        Raises:
            NotFoundError: 如果模型不存在。
            ValueError: 如果模型为内置模型，不允许删除。
        """
        model = await model_repo.get_by_id(session, model_id)
        if not model:
            raise NotFoundError(f"Model with id {model_id} not found")
        if model.is_builtin:
            raise ValueError("内置模型不允许删除")
        success = await model_repo.delete_by_id(session, model_id)
        if not success:
            raise NotFoundError(f"Model with id {model_id} not found")
        await session.commit()

