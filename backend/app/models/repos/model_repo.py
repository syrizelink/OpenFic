# -*- coding: utf-8 -*-
"""
Model Repository - 模型数据访问层。
"""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

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
)
from app.models.entities.model_provider import ModelProvider


async def get_all(session: AsyncSession) -> list[Model]:
    """
    获取所有模型。

    Args:
        session: 数据库 session。

    Returns:
        模型列表。
    """
    result = await session.execute(select(Model))
    return list(result.scalars().all())


async def get_by_provider_id(session: AsyncSession, provider_id: str) -> list[Model]:
    """
    根据提供商 ID 获取模型列表。

    Args:
        session: 数据库 session。
        provider_id: 提供商 ID。

    Returns:
        模型列表。
    """
    result = await session.execute(
        select(Model).where(col(Model.provider_id) == provider_id)
    )
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, model_id: str) -> Model | None:
    """
    根据 ID 获取模型。

    Args:
        session: 数据库 session。
        model_id: 模型 ID。

    Returns:
        模型实例，如果不存在则返回 None。
    """
    result = await session.execute(select(Model).where(col(Model.id) == model_id))
    return result.scalar_one_or_none()


async def exists_by_name(
    session: AsyncSession, name: str, *, exclude_model_id: str | None = None
) -> bool:
    """检查是否存在同名模型，可排除当前编辑的模型。"""
    statement = select(col(Model.id)).where(col(Model.name) == name)
    if exclude_model_id is not None:
        statement = statement.where(col(Model.id) != exclude_model_id)
    result = await session.execute(statement.limit(1))
    return result.scalar_one_or_none() is not None


async def get_by_legacy_agent_config(
    session: AsyncSession,
    *,
    model_id: str,
    provider_type: str,
    base_url: str,
) -> Model | None:
    """Find the unique current model matching a checkpoint created before model IDs persisted."""
    result = await session.execute(
        select(Model)
        .join(ModelProvider, col(Model.provider_id) == col(ModelProvider.id))
        .where(
            col(Model.model_id) == model_id,
            col(ModelProvider.provider_type) == provider_type,
            col(ModelProvider.url) == base_url,
        )
    )
    matches = list(result.scalars().all())
    return matches[0] if len(matches) == 1 else None


async def create(
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
        创建的模型实例。
    """
    model = Model(
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
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model


async def update(
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
) -> Model | None:
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
        更新后的模型实例，如果不存在则返回 None。
    """
    model = await get_by_id(session, model_id)
    if not model:
        return None

    if name is not None:
        model.name = name
    if remark is not None:
        model.remark = remark
    if provider_id is not None:
        model.provider_id = provider_id
    if model_identifier is not None:
        model.model_id = model_identifier
    if task_type is not None:
        model.task_type = task_type
    if temperature is not None:
        model.temperature = temperature
    if top_p is not None:
        model.top_p = top_p
    if top_k is not None:
        model.top_k = top_k
    if min_p is not None:
        model.min_p = min_p
    if top_a is not None:
        model.top_a = top_a
    if frequency_penalty is not None:
        model.frequency_penalty = frequency_penalty
    if presence_penalty is not None:
        model.presence_penalty = presence_penalty
    if repetition_penalty is not None:
        model.repetition_penalty = repetition_penalty
    if max_tokens is not None:
        model.max_tokens = max_tokens
    if context_length is not None:
        model.context_length = context_length
    if dimensions is not None:
        model.dimensions = dimensions

    model.updated_at = datetime.now(UTC)
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model


async def delete_by_id(session: AsyncSession, model_id: str) -> bool:
    """
    删除模型。

    Args:
        session: 数据库 session。
        model_id: 模型 ID。

    Returns:
        是否成功删除。
    """
    result = await session.execute(delete(Model).where(col(Model.id) == model_id))
    return cast("CursorResult[Any]", result).rowcount > 0
