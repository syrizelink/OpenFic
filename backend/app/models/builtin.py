# -*- coding: utf-8 -*-
"""
Builtin models - 基于 fastembed 的内置向量与重排模型定义。

内置模型使用固定 ID，应用启动时幂等地写入数据库，标记为 is_builtin，
不可通过 API 删除或编辑。运行时由 fastembed 在本地执行（有 GPU 用 GPU，
无 CUDA 自动降级到 CPU）。
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.models.entities.model import Model
from app.models.entities.model_provider import ModelProvider

BUILTIN_PROVIDER_ID = "builtin-local"
BUILTIN_PROVIDER_TYPE = "builtin"
BUILTIN_PROVIDER_URL = "builtin://local"
BUILTIN_PROVIDER_NAME = "内置本地模型"

BUILTIN_EMBEDDING_MODEL_ID = "builtin-embedding-bge-small-zh-v1.5"
BUILTIN_EMBEDDING_FASTEMBED_NAME = "BAAI/bge-small-zh-v1.5"
BUILTIN_EMBEDDING_MODEL_NAME = "bge-small-zh-v1.5"
BUILTIN_EMBEDDING_DIMENSIONS = 512

BUILTIN_RERANK_MODEL_ID = "builtin-rerank-ms-marco-minilm-l6-v2"
BUILTIN_RERANK_FASTEMBED_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"
BUILTIN_RERANK_MODEL_NAME = "ms-marco-MiniLM-L-6-v2"


@dataclass(frozen=True)
class BuiltinModelSpec:
    """内置模型规格。"""

    id: str
    name: str
    model_id: str
    task_type: str
    dimensions: int | None


BUILTIN_MODELS: tuple[BuiltinModelSpec, ...] = (
    BuiltinModelSpec(
        id=BUILTIN_EMBEDDING_MODEL_ID,
        name=BUILTIN_EMBEDDING_MODEL_NAME,
        model_id=BUILTIN_EMBEDDING_FASTEMBED_NAME,
        task_type="embedding",
        dimensions=BUILTIN_EMBEDDING_DIMENSIONS,
    ),
    BuiltinModelSpec(
        id=BUILTIN_RERANK_MODEL_ID,
        name=BUILTIN_RERANK_MODEL_NAME,
        model_id=BUILTIN_RERANK_FASTEMBED_NAME,
        task_type="rerank",
        dimensions=None,
    ),
)


def is_builtin_model(model: Model) -> bool:
    return bool(model.is_builtin)


def is_builtin_provider(provider: ModelProvider) -> bool:
    return bool(provider.is_builtin)


async def seed_builtin_models(session: AsyncSession) -> None:
    """幂等地写入内置提供商与内置模型。"""
    provider = await session.execute(
        select(ModelProvider).where(col(ModelProvider.id) == BUILTIN_PROVIDER_ID)
    )
    provider_row = provider.scalar_one_or_none()

    if provider_row is None:
        provider_row = ModelProvider(
            id=BUILTIN_PROVIDER_ID,
            name=BUILTIN_PROVIDER_NAME,
            url=BUILTIN_PROVIDER_URL,
            api_key_encrypted="",
            provider_type=BUILTIN_PROVIDER_TYPE,
            icon_path=None,
            is_builtin=True,
        )
        session.add(provider_row)
        await session.flush()
        logger.debug("Created builtin provider")
    elif not provider_row.is_builtin:
        provider_row.is_builtin = True

    for spec in BUILTIN_MODELS:
        existing = await session.execute(
            select(Model).where(col(Model.id) == spec.id)
        )
        model_row = existing.scalar_one_or_none()
        if model_row is None:
            model_row = Model(
                id=spec.id,
                name=spec.name,
                remark="",
                provider_id=BUILTIN_PROVIDER_ID,
                model_id=spec.model_id,
                task_type=spec.task_type,
                tags="[]",
                dimensions=spec.dimensions,
                is_builtin=True,
            )
            session.add(model_row)
            await session.flush()
            logger.debug("Created builtin model: {} ({})", spec.name, spec.task_type)
        elif not model_row.is_builtin:
            model_row.is_builtin = True

    await session.commit()


__all__ = [
    "BUILTIN_PROVIDER_ID",
    "BUILTIN_PROVIDER_TYPE",
    "BUILTIN_PROVIDER_URL",
    "BUILTIN_PROVIDER_NAME",
    "BUILTIN_EMBEDDING_MODEL_ID",
    "BUILTIN_EMBEDDING_FASTEMBED_NAME",
    "BUILTIN_EMBEDDING_DIMENSIONS",
    "BUILTIN_RERANK_MODEL_ID",
    "BUILTIN_RERANK_FASTEMBED_NAME",
    "BUILTIN_MODELS",
    "BuiltinModelSpec",
    "is_builtin_model",
    "is_builtin_provider",
    "seed_builtin_models",
]
