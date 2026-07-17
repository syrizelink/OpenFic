# -*- coding: utf-8 -*-
"""
Model 数据模型。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id
from app.models.clients.model_params import (
    DEFAULT_CONTEXT_LENGTH,
    MAX_CONTEXT_LENGTH,
)


class Model(SQLModel, table=True):
    """
    模型配置模型。

    Attributes:
        id: 模型唯一标识符（nanoid）。
        name: 模型名称。
        remark: 备注。
        provider_id: 关联的提供商 ID。
        model_id: 从提供商获取的模型 ID。
        task_type: 任务类型（llm、embedding 或 rerank）。
        temperature: Temperature 参数（LLM 专用）。
        top_p: Top P 参数（LLM 专用）。
        top_k: Top K 参数（LLM 专用）。
        min_p: Min P 参数（LLM 专用）。
        top_a: Top A 参数（LLM 专用）。
        frequency_penalty: Frequency Penalty 参数（LLM 专用）。
        presence_penalty: Presence Penalty 参数（LLM 专用）。
        repetition_penalty: Repetition Penalty 参数（LLM 专用）。
        max_tokens: Max Tokens 参数（LLM 专用）。
        context_length: 上下文长度（LLM 专用）。
        dimensions: Embedding 维度（Embedding 专用）。
        created_at: 创建时间。
        updated_at: 上次修改时间。
    """

    __tablename__ = "models"

    id: str = Field(default_factory=generate_id, primary_key=True)
    name: str = Field(max_length=200)
    remark: str = Field(default="", max_length=500)
    provider_id: str = Field(foreign_key="model_providers.id", index=True)
    model_id: str = Field(
        max_length=200, description="Model ID from the provider (e.g., gpt-4, claude-3-opus)"
    )
    task_type: str = Field(
        default="llm",
        max_length=20,
        index=True,
        description="Task type: llm, embedding, or rerank",
    )
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=0, le=128)
    min_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_a: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    repetition_penalty: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    context_length: int = Field(default=DEFAULT_CONTEXT_LENGTH, ge=0, le=MAX_CONTEXT_LENGTH)

    # Embedding parameters (nullable)
    dimensions: int | None = Field(default=None, ge=1, description="Embedding dimensions")

    is_builtin: bool = Field(default=False, description="是否为内置模型（不可删除/编辑）")

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
