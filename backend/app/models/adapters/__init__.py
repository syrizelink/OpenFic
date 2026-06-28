# -*- coding: utf-8 -*-
"""
Adapters Module - Provider适配器模块。

每个Provider对应一个Adapter，支持获取LLM和Embedding两种类型的模型列表。
"""

from app.models.adapters.base import BaseAdapter
from app.models.adapters.anthropic import AnthropicAdapter
from app.models.adapters.deepseek import DeepSeekAdapter
from app.models.adapters.google_genai import GoogleGenAIAdapter
from app.models.adapters.mistral import MistralAdapter
from app.models.adapters.openai import OpenAIAdapter
from app.models.adapters.openai_compat_family import (
    AmazonNovaAdapter,
    CohereAdapter,
    GroqAdapter,
    HuggingFaceAdapter,
    NvidiaAIEndpointsAdapter,
    OllamaAdapter,
)
from app.models.adapters.openai_compatible import OpenAICompatibleAdapter
from app.models.adapters.openrouter import OpenRouterAdapter

__all__ = [
    "BaseAdapter",
    "AmazonNovaAdapter",
    "AnthropicAdapter",
    "CohereAdapter",
    "DeepSeekAdapter",
    "GoogleGenAIAdapter",
    "GroqAdapter",
    "HuggingFaceAdapter",
    "MistralAdapter",
    "NvidiaAIEndpointsAdapter",
    "OllamaAdapter",
    "OpenAIAdapter",
    "OpenAICompatibleAdapter",
    "OpenRouterAdapter",
]

