# -*- coding: utf-8 -*-
"""
ModelProvider API Schemas - 模型服务提供商请求/响应模型。
"""

from typing import Any

from pydantic import BaseModel, Field


class CatalogMatchResponse(BaseModel):
    """Matched catalog provider metadata for a saved provider."""

    catalog_provider_type: str = Field(description="匹配到的 catalog provider_type")
    display_name: str = Field(description="Catalog 提供商显示名")
    default_url: str | None = Field(default=None, description="Catalog 默认 URL")
    api: str | None = Field(default=None, description="Models.dev api 字段")
    icon_path: str | None = Field(default=None, description="内置图标路径")
    models_dev_provider_id: str | None = Field(
        default=None, description="Models.dev provider id"
    )
    matched_via: str = Field(description="provider_type 或 api")


class ModelProviderResponse(BaseModel):
    """提供商响应。"""

    id: str = Field(description="提供商 ID")
    name: str = Field(description="提供商名称/备注")
    url: str = Field(description="服务 URL")
    provider_type: str = Field(description="提供商类型")
    supported_task_types: list[str] = Field(
        description="支持的任务类型列表 (llm, embedding, rerank)"
    )
    icon_path: str | None = Field(description="Catalog 图标路径")
    is_builtin: bool = Field(default=False, description="是否为内置提供商")
    catalog_match: CatalogMatchResponse | None = Field(
        default=None, description="匹配到的 catalog 提供商元数据"
    )
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


class ModelProviderValidateRequest(BaseModel):
    """验证提供商连接请求。"""

    provider_type: str = Field(description="提供商类型")
    url: str = Field(description="服务 URL")
    api_key: str = Field(description="API Key")


class AvailableModelMetadata(BaseModel):
    """模型展示元数据。"""

    release_date: str | None = Field(default=None, description="模型发布日期")
    reasoning: bool | None = Field(default=None, description="是否支持 reasoning")
    tool_call: bool | None = Field(default=None, description="是否支持 tool call")
    modalities: dict[str, list[str]] | None = Field(
        default=None, description="输入输出模态"
    )
    limit: dict[str, Any] | str | int | None = Field(
        default=None, description="上下文与输出限制"
    )
    cost: dict[str, Any] | str | int | None = Field(
        default=None, description="价格元数据"
    )


class AvailableModel(BaseModel):
    """可用模型。"""

    id: str = Field(description="模型 ID")
    name: str = Field(description="模型名称")
    task_type: str | None = Field(default=None, description="任务类型")
    metadata: AvailableModelMetadata | None = Field(
        default=None, description="匹配到的 catalog 元数据"
    )


class ModelProviderValidateResponse(BaseModel):
    """验证提供商连接响应。"""

    success: bool = Field(description="是否验证成功")
    message: str = Field(description="消息")
    models: list[AvailableModel] = Field(description="可用模型列表")
