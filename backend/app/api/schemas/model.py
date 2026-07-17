# -*- coding: utf-8 -*-
"""
Model API Schemas - 模型请求/响应模型。
"""

from typing import Literal

from pydantic import BaseModel, Field

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
    MAX_CONTEXT_LENGTH,
)

TaskType = Literal["llm", "embedding", "rerank"]


class ModelResponse(BaseModel):
    """模型响应。"""

    id: str = Field(description="模型 ID")
    name: str = Field(description="模型名称")
    remark: str = Field(description="备注")
    provider_id: str = Field(description="关联的提供商 ID")
    model_id: str = Field(description="从提供商获取的模型 ID")
    task_type: TaskType = Field(description="任务类型（llm、embedding 或 rerank）")
    temperature: float | None = Field(description="Temperature 参数（LLM 专用）")
    top_p: float | None = Field(description="Top P 参数（LLM 专用）")
    top_k: int | None = Field(description="Top K 参数（LLM 专用）")
    min_p: float | None = Field(description="Min P 参数（LLM 专用）")
    top_a: float | None = Field(description="Top A 参数（LLM 专用）")
    frequency_penalty: float | None = Field(description="Frequency Penalty 参数（LLM 专用）")
    presence_penalty: float | None = Field(description="Presence Penalty 参数（LLM 专用）")
    repetition_penalty: float | None = Field(description="Repetition Penalty 参数（LLM 专用）")
    max_tokens: int | None = Field(description="Max Tokens 参数（LLM 专用）")
    context_length: int = Field(description="上下文长度（LLM 专用）")
    dimensions: int | None = Field(description="Embedding 维度（Embedding 专用）")
    is_builtin: bool = Field(default=False, description="是否为内置模型")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


class ModelCreateRequest(BaseModel):
    """创建模型请求。"""

    name: str = Field(description="模型名称")
    provider_id: str = Field(description="关联的提供商 ID")
    model_id: str = Field(description="从提供商获取的模型 ID")
    task_type: TaskType = Field(
        default="llm", description="任务类型（llm、embedding 或 rerank）"
    )
    remark: str = Field(default="", description="备注")
    temperature: float | None = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    top_p: float | None = Field(default=DEFAULT_TOP_P, ge=0.0, le=1.0)
    top_k: int | None = Field(default=DEFAULT_TOP_K, ge=0, le=128)
    min_p: float | None = Field(default=DEFAULT_MIN_P, ge=0.0, le=1.0)
    top_a: float | None = Field(default=DEFAULT_TOP_A, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=DEFAULT_FREQUENCY_PENALTY, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=DEFAULT_PRESENCE_PENALTY, ge=-2.0, le=2.0)
    repetition_penalty: float | None = Field(default=DEFAULT_REPETITION_PENALTY, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, description="Max Tokens 参数（LLM 专用）")
    context_length: int = Field(default=DEFAULT_CONTEXT_LENGTH, ge=0, le=MAX_CONTEXT_LENGTH)
    dimensions: int | None = Field(default=None, description="Embedding 维度（Embedding 专用）")


class ModelUpdateRequest(BaseModel):
    """更新模型请求。"""

    name: str | None = Field(default=None, description="模型名称")
    remark: str | None = Field(default=None, description="备注")
    provider_id: str | None = Field(default=None, description="关联的提供商 ID")
    model_id: str | None = Field(default=None, description="从提供商获取的模型 ID")
    task_type: TaskType | None = Field(
        default=None, description="任务类型（llm、embedding 或 rerank）"
    )
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=0, le=128)
    min_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_a: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    repetition_penalty: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, description="Max Tokens 参数（LLM 专用）")
    context_length: int | None = Field(default=None, ge=0, le=MAX_CONTEXT_LENGTH)
    dimensions: int | None = Field(default=None, description="Embedding 维度（Embedding 专用）")
