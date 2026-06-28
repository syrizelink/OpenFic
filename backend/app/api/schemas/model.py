# -*- coding: utf-8 -*-
"""
Model API Schemas - 模型请求/响应模型。
"""

from typing import Literal

from pydantic import BaseModel, Field

DeepSeekReasoningEffort = Literal["high", "max"]
DeepSeekThinkingType = Literal["enabled", "disabled"]
TaskType = Literal["llm", "embedding", "rerank"]


class ModelResponse(BaseModel):
    """模型响应。"""

    id: str = Field(description="模型 ID")
    name: str = Field(description="模型名称")
    remark: str = Field(description="备注")
    provider_id: str = Field(description="关联的提供商 ID")
    model_id: str = Field(description="从提供商获取的模型 ID")
    task_type: TaskType = Field(description="任务类型（llm、embedding 或 rerank）")
    tags: list[str] = Field(description="标签列表")
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
    deepseek_reasoning_effort: str | None = Field(
        description="DeepSeek 推理强度（DeepSeek 专用）"
    )
    deepseek_thinking_type: str | None = Field(
        description="DeepSeek thinking 开关（DeepSeek 专用）"
    )
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
    tags: list[str] = Field(default_factory=list, description="标签列表")
    temperature: float | None = Field(default=None, description="Temperature 参数（LLM 专用）")
    top_p: float | None = Field(default=None, description="Top P 参数（LLM 专用）")
    top_k: int | None = Field(default=None, description="Top K 参数（LLM 专用）")
    min_p: float | None = Field(default=None, description="Min P 参数（LLM 专用）")
    top_a: float | None = Field(default=None, description="Top A 参数（LLM 专用）")
    frequency_penalty: float | None = Field(
        default=None, description="Frequency Penalty 参数（LLM 专用）"
    )
    presence_penalty: float | None = Field(
        default=None, description="Presence Penalty 参数（LLM 专用）"
    )
    repetition_penalty: float | None = Field(
        default=None, description="Repetition Penalty 参数（LLM 专用）"
    )
    max_tokens: int | None = Field(default=None, description="Max Tokens 参数（LLM 专用）")
    context_length: int | None = Field(default=128000, ge=1, description="上下文长度（LLM 专用）")
    deepseek_reasoning_effort: DeepSeekReasoningEffort | None = Field(
        default="high", description="DeepSeek 推理强度（DeepSeek 专用）"
    )
    deepseek_thinking_type: DeepSeekThinkingType | None = Field(
        default="enabled", description="DeepSeek thinking 开关（DeepSeek 专用）"
    )
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
    tags: list[str] | None = Field(default=None, description="标签列表")
    temperature: float | None = Field(default=None, description="Temperature 参数（LLM 专用）")
    top_p: float | None = Field(default=None, description="Top P 参数（LLM 专用）")
    top_k: int | None = Field(default=None, description="Top K 参数（LLM 专用)")
    min_p: float | None = Field(default=None, description="Min P 参数（LLM 专用）")
    top_a: float | None = Field(default=None, description="Top A 参数（LLM 专用）")
    frequency_penalty: float | None = Field(
        default=None, description="Frequency Penalty 参数（LLM 专用）"
    )
    presence_penalty: float | None = Field(
        default=None, description="Presence Penalty 参数（LLM 专用）"
    )
    repetition_penalty: float | None = Field(
        default=None, description="Repetition Penalty 参数（LLM 专用）"
    )
    max_tokens: int | None = Field(default=None, description="Max Tokens 参数（LLM 专用）")
    context_length: int | None = Field(default=None, description="上下文长度（LLM 专用）")
    deepseek_reasoning_effort: DeepSeekReasoningEffort | None = Field(
        default=None, description="DeepSeek 推理强度（DeepSeek 专用）"
    )
    deepseek_thinking_type: DeepSeekThinkingType | None = Field(
        default=None, description="DeepSeek thinking 开关（DeepSeek 专用）"
    )
    dimensions: int | None = Field(default=None, description="Embedding 维度（Embedding 专用）")


class TagsResponse(BaseModel):
    """标签响应。"""

    tags: list[str] = Field(description="所有已使用的标签列表")
