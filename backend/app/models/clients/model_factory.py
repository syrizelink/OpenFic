from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.models.clients.deepseek_payload import patch_deepseek_reasoning_payload
from app.models.clients.model_params import (
    DEFAULT_FREQUENCY_PENALTY,
    DEFAULT_MIN_P,
    DEFAULT_PRESENCE_PENALTY,
    DEFAULT_REPETITION_PENALTY,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_A,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
    ReasoningEffort,
    is_non_default,
    with_default,
)


@dataclass
class ModelConfig:
    provider_type: str
    base_url: str
    api_key: str
    model_id: str
    max_context_tokens: int | None = None
    temperature: float | None = DEFAULT_TEMPERATURE
    top_p: float | None = DEFAULT_TOP_P
    top_k: int | None = DEFAULT_TOP_K
    min_p: float | None = DEFAULT_MIN_P
    top_a: float | None = DEFAULT_TOP_A
    max_tokens: int | None = None
    frequency_penalty: float | None = DEFAULT_FREQUENCY_PENALTY
    presence_penalty: float | None = DEFAULT_PRESENCE_PENALTY
    repetition_penalty: float | None = DEFAULT_REPETITION_PENALTY
    reasoning_effort: ReasoningEffort | None = None

    def __post_init__(self) -> None:
        self.temperature = with_default(self.temperature, DEFAULT_TEMPERATURE)
        self.top_p = with_default(self.top_p, DEFAULT_TOP_P)
        self.top_k = with_default(self.top_k, DEFAULT_TOP_K)
        self.min_p = with_default(self.min_p, DEFAULT_MIN_P)
        self.top_a = with_default(self.top_a, DEFAULT_TOP_A)
        self.frequency_penalty = with_default(
            self.frequency_penalty, DEFAULT_FREQUENCY_PENALTY
        )
        self.presence_penalty = with_default(
            self.presence_penalty, DEFAULT_PRESENCE_PENALTY
        )
        self.repetition_penalty = with_default(
            self.repetition_penalty, DEFAULT_REPETITION_PENALTY
        )


def _compact_kwargs(**kwargs: Any) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}


def _non_default(value: Any, default: Any) -> Any | None:
    return value if is_non_default(value, default) else None


def _openai_compatible_kwargs(config: ModelConfig) -> dict[str, Any]:
    kwargs = _compact_kwargs(
        model=config.model_id,
        api_key=config.api_key,
        base_url=config.base_url or None,
        temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
        top_p=_non_default(config.top_p, DEFAULT_TOP_P),
        max_tokens=config.max_tokens,
        frequency_penalty=_non_default(
            config.frequency_penalty, DEFAULT_FREQUENCY_PENALTY
        ),
        presence_penalty=_non_default(config.presence_penalty, DEFAULT_PRESENCE_PENALTY),
        reasoning_effort=config.reasoning_effort,
        max_retries=0,
    )
    extra_body = {
        name: value
        for name, value, default in (
            ("top_k", config.top_k, DEFAULT_TOP_K),
            ("min_p", config.min_p, DEFAULT_MIN_P),
            ("top_a", config.top_a, DEFAULT_TOP_A),
            ("repetition_penalty", config.repetition_penalty, DEFAULT_REPETITION_PENALTY),
        )
        if is_non_default(value, default)
    }
    if extra_body:
        kwargs["extra_body"] = extra_body
    return kwargs


def create_chat_model(config: ModelConfig) -> BaseChatModel:
    provider = config.provider_type

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(**_compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            top_k=_non_default(config.top_k, DEFAULT_TOP_K),
            max_tokens=config.max_tokens or 4096,
            max_retries=0,
        ))

    if provider == "google-genai":
        from langchain_google_genai import ChatGoogleGenerativeAI

        google_kwargs = _compact_kwargs(
            model=config.model_id,
            google_api_key=config.api_key,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            top_k=_non_default(config.top_k, DEFAULT_TOP_K),
            max_output_tokens=config.max_tokens,
            max_retries=1,
        )
        if config.base_url:
            google_kwargs["client_options"] = {"api_endpoint": config.base_url}
        return ChatGoogleGenerativeAI(**google_kwargs)

    if provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek

        class ChatDeepSeekWithReasoningPayload(ChatDeepSeek):
            def _get_request_payload(
                self,
                input_: Any,
                *,
                stop: list[str] | None = None,
                **kwargs: Any,
            ) -> dict[str, Any]:
                payload = super()._get_request_payload(input_, stop=stop, **kwargs)
                patch_deepseek_reasoning_payload(input_, payload)
                return payload

        return ChatDeepSeekWithReasoningPayload(**_compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            max_tokens=config.max_tokens,
            reasoning_effort=config.reasoning_effort,
            max_retries=0,
        ))

    if provider == "mistral":
        from langchain_mistralai import ChatMistralAI

        return ChatMistralAI(**_compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            max_tokens=config.max_tokens,
            max_retries=0,
        ))

    if provider == "openrouter":
        from langchain_openrouter import ChatOpenRouter

        return ChatOpenRouter(**_compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            max_tokens=config.max_tokens,
            frequency_penalty=_non_default(
                config.frequency_penalty, DEFAULT_FREQUENCY_PENALTY
            ),
            presence_penalty=_non_default(
                config.presence_penalty, DEFAULT_PRESENCE_PENALTY
            ),
            max_retries=0,
        ))

    if provider == "groq":
        from langchain_groq import ChatGroq

        groq_kwargs = _compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            max_tokens=config.max_tokens,
            max_retries=0,
        )
        if config.top_p is not None:
            groq_kwargs["model_kwargs"] = {"top_p": config.top_p}
        return ChatGroq(**groq_kwargs)

    if provider == "cohere":
        from langchain_cohere import ChatCohere

        cohere_kwargs = _compact_kwargs(
            model=config.model_id,
            cohere_api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
        )
        if config.max_tokens is not None:
            cohere_kwargs["model_kwargs"] = {"max_tokens": config.max_tokens}
        return ChatCohere(**cohere_kwargs)

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(**_compact_kwargs(
            model=config.model_id,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            top_k=_non_default(config.top_k, DEFAULT_TOP_K),
            num_predict=config.max_tokens,
        ))

    if provider == "amazon-nova":
        from langchain_amazon_nova import ChatAmazonNova

        return ChatAmazonNova(**_compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            max_tokens=config.max_tokens,
            max_retries=0,
        ))

    if provider == "nvidia-ai-endpoints":
        from langchain_nvidia_ai_endpoints import ChatNVIDIA

        return ChatNVIDIA(**_compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            max_completion_tokens=config.max_tokens,
        ))

    # OpenAI-compatible fallback (openai, huggingface, openai-compatible, unknown)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(**_openai_compatible_kwargs(config))
