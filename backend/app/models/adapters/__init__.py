# -*- coding: utf-8 -*-
"""
Adapters Module - modul adapter Provider.

Setiap Provider memiliki satu Adapter, mendukung pengambilan daftar model
untuk dua jenis: LLM dan embedding.
"""

from app.models.adapters.base import BaseAdapter
from app.models.adapters.anthropic import AnthropicAdapter
from app.models.adapters.anthropic_compatible import AnthropicCompatibleAdapter
from app.models.adapters.deepseek import DeepSeekAdapter
from app.models.adapters.gemini_compatible import GeminiCompatibleAdapter
from app.models.adapters.google_genai import GoogleGenAIAdapter
from app.models.adapters.mistral import MistralAdapter
from app.models.adapters.openai import OpenAIAdapter
from app.models.adapters.openai_compat_family import (
    AmazonNovaAdapter,
    CohereAdapter,
    GroqAdapter,
    HuggingFaceAdapter,
    NvidiaAIEndpointsAdapter,
)
from app.models.adapters.openai_compatible import OpenAICompatibleAdapter
from app.models.adapters.openai_responses_compatible import OpenAIResponsesCompatibleAdapter
from app.models.adapters.openrouter import OpenRouterAdapter

__all__ = [
    "BaseAdapter",
    "AmazonNovaAdapter",
    "AnthropicAdapter",
    "AnthropicCompatibleAdapter",
    "CohereAdapter",
    "DeepSeekAdapter",
    "GeminiCompatibleAdapter",
    "GoogleGenAIAdapter",
    "GroqAdapter",
    "HuggingFaceAdapter",
    "MistralAdapter",
    "NvidiaAIEndpointsAdapter",
    "OpenAIAdapter",
    "OpenAICompatibleAdapter",
    "OpenAIResponsesCompatibleAdapter",
    "OpenRouterAdapter",
]

