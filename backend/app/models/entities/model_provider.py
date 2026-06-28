# -*- coding: utf-8 -*-
"""
ModelProvider 数据模型。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class ModelProvider(SQLModel, table=True):
    """
    模型服务提供商模型。

    Attributes:
        id: 提供商唯一标识符（nanoid）。
        name: 提供商名称/备注（非必须，不填则显示为 URL）。
        url: 服务 URL。
        api_key_encrypted: 加密后的 API Key。
        provider_type: 提供商类型（Anthropic、OpenAI、Deepseek 等）。
        icon_path: 图标文件路径（相对于icons/model目录）。
        created_at: 创建时间。
        updated_at: 上次修改时间。
    """

    __tablename__ = "model_providers"

    id: str = Field(default_factory=generate_id, primary_key=True)
    name: str = Field(default="", max_length=200)
    url: str = Field(max_length=500)
    api_key_encrypted: str = Field(max_length=1000)
    provider_type: str = Field(
        max_length=50,
        description=(
            "Provider type: anthropic, openai, google-genai, ollama, groq, "
            "huggingface, mistral, nvidia-ai-endpoints, cohere, openrouter, "
            "amazon-nova, deepseek, openai-compatible"
        ),
    )
    icon_path: str | None = Field(default=None, max_length=500)
    is_builtin: bool = Field(default=False, description="是否为内置提供商（不可删除/编辑）")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
