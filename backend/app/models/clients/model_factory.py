from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from app.core.ids import generate_id
from app.core.utils.tiktoken import seed_bundled_encodings
from app.models.adapters.anthropic_compatible import ANTHROPIC_COMPATIBLE_PROVIDER_TYPES
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
    ReasoningEffortInput,
    is_non_default,
    normalize_reasoning_effort,
    with_default,
)
from app.models.helpers.openrouter_attribution import (
    OPENROUTER_APP_CATEGORIES,
    OPENROUTER_APP_TITLE,
    OPENROUTER_APP_URL,
)
from app.models.helpers.requesty_attribution import get_requesty_attribution_headers


@dataclass
class ModelConfig:
    provider_type: str
    base_url: str
    api_key: str
    model_id: str
    custom_headers: dict[str, str] | None = None
    session_id: str | None = None
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
    reasoning_effort: ReasoningEffortInput | None = None

    def __post_init__(self) -> None:
        if self.reasoning_effort == "off":
            self.reasoning_effort = "auto"
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


def _enabled_reasoning_effort(config: ModelConfig) -> ReasoningEffort | None:
    if config.reasoning_effort is None:
        return None
    reasoning_effort = normalize_reasoning_effort(config.reasoning_effort)
    return None if reasoning_effort == "auto" else reasoning_effort


def _three_level_reasoning_effort(
    reasoning_effort: ReasoningEffort | None,
) -> str | None:
    if reasoning_effort is None:
        return None
    return "high" if reasoning_effort in {"xhigh", "max"} else reasoning_effort


def _request_timeout() -> tuple[float, float]:
    from app.settings import settings

    return (settings.llm_connect_timeout, settings.llm_request_timeout)


def _stream_chunk_timeout() -> float | None:
    from app.settings import settings

    return settings.llm_chunk_timeout


def _gemini_compatible_base_url(base_url: str) -> str:
    normalized_url = base_url.rstrip("/")
    return normalized_url.removesuffix("/v1beta")


def _application_user_agent() -> str:
    from app.settings import settings

    return f"{settings.app_name}/{settings.app_version}"


def _set_header(headers: dict[str, str], name: str, value: str) -> None:
    for existing_name in tuple(headers):
        if existing_name.lower() == name.lower():
            del headers[existing_name]
    headers[name] = value


def _is_opencode_provider(config: ModelConfig) -> bool:
    if config.provider_type.lower().startswith("opencode"):
        return True
    return (urlparse(config.base_url).hostname or "").lower() == "opencode.ai"


def _model_request_headers(config: ModelConfig) -> dict[str, str]:
    headers = dict(config.custom_headers or {})
    if config.provider_type == "requesty":
        headers = {**get_requesty_attribution_headers(), **headers}
    _set_header(headers, "User-Agent", _application_user_agent())
    is_opencode_provider = _is_opencode_provider(config)
    if is_opencode_provider:
        if not config.session_id:
            config.session_id = f"openfic-{generate_id()}"
        _set_header(headers, "x-opencode-session", config.session_id)
    return headers


def _update_http_client_headers(client: Any, headers: dict[str, str]) -> None:
    request_client = getattr(client, "_client", client)
    client_headers = getattr(request_client, "headers", None)
    if client_headers is not None:
        client_headers.update(headers)


def _openai_compatible_kwargs(config: ModelConfig) -> dict[str, Any]:
    kwargs = _compact_kwargs(
        model=config.model_id,
        api_key=config.api_key,
        base_url=config.base_url or None,
        default_headers=_model_request_headers(config),
        temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
        top_p=_non_default(config.top_p, DEFAULT_TOP_P),
        max_tokens=config.max_tokens,
        frequency_penalty=_non_default(
            config.frequency_penalty, DEFAULT_FREQUENCY_PENALTY
        ),
        presence_penalty=_non_default(config.presence_penalty, DEFAULT_PRESENCE_PENALTY),
        reasoning_effort=_enabled_reasoning_effort(config),
        max_retries=0,
        stream_usage=True,
        stream_chunk_timeout=_stream_chunk_timeout(),
        timeout=_request_timeout(),
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


def create_chat_model(config: ModelConfig) -> Runnable[LanguageModelInput, BaseMessage]:
    seed_bundled_encodings()
    provider = config.provider_type
    reasoning_effort = _enabled_reasoning_effort(config)

    if (
        provider == "anthropic"
        or provider == "anthropic-compatible"
        or provider in ANTHROPIC_COMPATIBLE_PROVIDER_TYPES
    ):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(**_compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            default_headers=_model_request_headers(config),
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            top_k=_non_default(config.top_k, DEFAULT_TOP_K),
            max_tokens=config.max_tokens or 4096,
            effort=reasoning_effort,
            max_retries=0,
            timeout=_request_timeout()[1],
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
            thinking_level=_three_level_reasoning_effort(reasoning_effort),
            additional_headers=_model_request_headers(config),
            max_retries=1,
        )
        if config.base_url:
            google_kwargs["client_options"] = {"api_endpoint": config.base_url}
        return ChatGoogleGenerativeAI(**google_kwargs)

    if provider == "gemini-compatible":
        from langchain_google_genai import ChatGoogleGenerativeAI

        gemini_kwargs = _compact_kwargs(
            model=config.model_id,
            google_api_key=config.api_key,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            top_k=_non_default(config.top_k, DEFAULT_TOP_K),
            max_output_tokens=config.max_tokens,
            thinking_level=_three_level_reasoning_effort(reasoning_effort),
            additional_headers=_model_request_headers(config),
            max_retries=0,
            api_version="v1beta",
        )
        if config.base_url:
            gemini_kwargs["client_options"] = {
                "api_endpoint": _gemini_compatible_base_url(config.base_url)
            }
        return ChatGoogleGenerativeAI(**gemini_kwargs)

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
            default_headers=_model_request_headers(config),
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            max_tokens=config.max_tokens,
            reasoning_effort=reasoning_effort,
            max_retries=0,
            stream_usage=True,
            stream_chunk_timeout=_stream_chunk_timeout(),
            timeout=_request_timeout(),
        ))

    if provider == "mistral":
        from langchain_mistralai import ChatMistralAI

        mistral_kwargs = _compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            max_tokens=config.max_tokens,
            max_retries=0,
            timeout=_request_timeout()[1],
        )
        if reasoning_effort:
            mistral_kwargs["model_kwargs"] = {"reasoning_effort": reasoning_effort}
        model = ChatMistralAI(**mistral_kwargs)
        headers = _model_request_headers(config)
        _update_http_client_headers(model.client, headers)
        _update_http_client_headers(model.async_client, headers)
        return model

    if provider == "openrouter":
        from langchain_openrouter import ChatOpenRouter

        model = ChatOpenRouter(**_compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            app_url=OPENROUTER_APP_URL,
            app_title=OPENROUTER_APP_TITLE,
            app_categories=list(OPENROUTER_APP_CATEGORIES),
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            max_tokens=config.max_tokens,
            frequency_penalty=_non_default(
                config.frequency_penalty, DEFAULT_FREQUENCY_PENALTY
            ),
            presence_penalty=_non_default(
                config.presence_penalty, DEFAULT_PRESENCE_PENALTY
            ),
            reasoning={"effort": reasoning_effort} if reasoning_effort else None,
            max_retries=0,
            timeout=int(_request_timeout()[1] * 1000),
        ))
        headers = _model_request_headers(config)
        _update_http_client_headers(model.client.sdk_configuration.client, headers)
        _update_http_client_headers(model.client.sdk_configuration.async_client, headers)
        return model

    if provider == "groq":
        from langchain_groq import ChatGroq

        groq_kwargs = _compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            max_tokens=config.max_tokens,
            reasoning_effort=_three_level_reasoning_effort(reasoning_effort),
            max_retries=0,
            timeout=_request_timeout(),
            default_headers=_model_request_headers(config),
        )
        if config.top_p is not None:
            groq_kwargs["model_kwargs"] = {"top_p": config.top_p}
        return ChatGroq(**groq_kwargs)

    if provider == "cohere":
        from langchain_cohere import ChatCohere

        class ChatCohereWithThinking(ChatCohere):
            @property
            def _default_params(self) -> dict[str, Any]:
                params = super()._default_params
                if reasoning_effort:
                    params["thinking"] = {
                        "type": "enabled",
                        "token_budget": {
                            "low": 1024,
                            "medium": 4096,
                            "high": 8192,
                            "xhigh": 16384,
                            "max": 16384,
                        }[reasoning_effort],
                    }
                return params

        cohere_kwargs = _compact_kwargs(
            model=config.model_id,
            cohere_api_key=config.api_key,
            user_agent=_application_user_agent(),
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
        )
        if config.max_tokens is not None:
            cohere_kwargs["model_kwargs"] = {"max_tokens": config.max_tokens}
        return ChatCohereWithThinking(**cohere_kwargs)

    if provider == "amazon-nova":
        from langchain_amazon_nova import ChatAmazonNova

        model = ChatAmazonNova(**_compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            max_tokens=config.max_tokens,
            reasoning_effort=_three_level_reasoning_effort(reasoning_effort),
            max_retries=0,
        ))
        headers = _model_request_headers(config)
        _update_http_client_headers(model.client, headers)
        _update_http_client_headers(model.async_client, headers)
        return model

    if provider == "openai-compatible-responses":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            **_openai_compatible_kwargs(config),
            use_responses_api=True,
        )

    if provider == "nvidia-ai-endpoints":
        from langchain_nvidia_ai_endpoints import ChatNVIDIA

        nvidia_kwargs = _compact_kwargs(
            model=config.model_id,
            api_key=config.api_key,
            base_url=config.base_url or None,
            temperature=_non_default(config.temperature, DEFAULT_TEMPERATURE),
            top_p=_non_default(config.top_p, DEFAULT_TOP_P),
            max_completion_tokens=config.max_tokens,
            default_headers=_model_request_headers(config),
        )
        model = ChatNVIDIA(**nvidia_kwargs)
        return model.with_thinking_mode(enabled=True) if reasoning_effort else model

    # OpenAI-compatible fallback (openai, huggingface, openai-compatible, unknown)
    from langchain_core.outputs import ChatGenerationChunk
    from langchain_openai import ChatOpenAI as _ChatOpenAI

    class ChatOpenAI(_ChatOpenAI):
        def _convert_chunk_to_generation_chunk(
            self,
            chunk: dict,
            default_chunk_class: type,
            base_generation_info: dict | None,
        ) -> ChatGenerationChunk | None:
            generation_chunk = super()._convert_chunk_to_generation_chunk(
                chunk,
                default_chunk_class,
                base_generation_info,
            )
            if generation_chunk is None:
                return None

            choices = chunk.get("choices")
            if not isinstance(choices, list) or not choices:
                return generation_chunk
            choice = choices[0]
            if not isinstance(choice, dict):
                return generation_chunk
            delta = choice.get("delta")
            reasoning_content = (
                delta.get("reasoning_content")
                if isinstance(delta, dict)
                else None
            )
            if isinstance(reasoning_content, str):
                generation_chunk.message.additional_kwargs["reasoning_content"] = (
                    reasoning_content
                )
            return generation_chunk

    return ChatOpenAI(**_openai_compatible_kwargs(config))
