"""Resolve Models.dev v1 routing from the local catalog, without network access."""

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from loguru import logger


_CUSTOM_PROVIDERS = {
    "openai-compatible",
    "openai-compatible-responses",
    "anthropic-compatible",
    "gemini-compatible",
    "openai-codex",
}
_SDK_PROVIDERS = {
    "@ai-sdk/openai": "openai-compatible-responses",
    "@ai-sdk/openai-compatible": "openai-compatible",
    "@ai-sdk/anthropic": "anthropic-compatible",
    "@ai-sdk/google": "gemini-compatible",
    "@ai-sdk/deepseek": "deepseek",
    "@ai-sdk/groq": "groq",
    "@ai-sdk/mistral": "mistral",
    "@ai-sdk/cohere": "cohere",
    "@openrouter/ai-sdk-provider": "openrouter",
}
_OPENAI_PROVIDERS = {
    "openai",
    "openai-compatible",
    "openai-compatible-responses",
    "huggingface",
    "ollama",
    "infistar",
}


@dataclass(frozen=True)
class ChatModelRoute:
    provider_type: str
    base_url: str
    google_api_version: str = "v1beta"


def _legacy_route(provider: str, model_id: str, base_url: str) -> ChatModelRoute:
    if provider not in {"opencode", "opencode-go"}:
        return ChatModelRoute(provider, base_url)
    model_id = model_id.lower()
    if model_id.startswith(("gpt-", "grok-", "muse-spark-", "muse-wonder-")):
        return ChatModelRoute("openai-compatible-responses", base_url)
    if model_id.startswith("claude-"):
        url = urlsplit(base_url)
        if url.hostname == "opencode.ai" and url.path.rstrip("/") in {
            "/inference/openai/v1",
            "/inference/go/openai/v1",
        }:
            path = (
                "/inference/go/anthropic"
                if provider == "opencode-go"
                else "/inference/anthropic"
            )
            base_url = urlunsplit(url._replace(path=path))
        return ChatModelRoute(
            "anthropic-compatible", base_url.rstrip("/").removesuffix("/v1")
        )
    if model_id.startswith("gemini-"):
        url = urlsplit(base_url)
        if url.hostname == "opencode.ai" and (
            provider == "opencode-go" or url.path.rstrip("/") == "/inference/openai/v1"
        ):
            return ChatModelRoute(
                "gemini-compatible",
                urlunsplit(
                    url._replace(
                        path="/inference/go/google"
                        if provider == "opencode-go"
                        else "/inference/google",
                        query="",
                        fragment="",
                    )
                ),
            )
        return ChatModelRoute(
            "gemini-compatible", base_url.rstrip("/").removesuffix("/v1"), "v1"
        )
    return ChatModelRoute(provider, base_url)


def resolve_chat_model_route(
    provider: str, model_id: str, base_url: str
) -> ChatModelRoute:
    # Explicit custom protocols and user gateways must not be overridden by a
    # catalog match, even when they use an official model ID or endpoint.
    if provider in _CUSTOM_PROVIDERS:
        return ChatModelRoute(provider, base_url)
    fallback = _legacy_route(provider, model_id, base_url)

    from app.models.catalog.service import ModelProviderCatalogService
    from app.models.registry import AdapterRegistry

    try:
        overrides = ModelProviderCatalogService().get_model_provider_config(
            provider, model_id
        )
    except (OSError, ValueError, TypeError):
        logger.warning("Unable to read local model routing; keeping provider defaults")
        return fallback

    npm = overrides.get("npm")
    if npm and npm not in _SDK_PROVIDERS:
        return fallback
    protocol = _SDK_PROVIDERS.get(npm, fallback.provider_type)
    shape = overrides.get("shape")
    uses_openai = protocol in _OPENAI_PROVIDERS or (
        not npm and protocol not in AdapterRegistry.list_providers()
    )
    if uses_openai and shape in {"responses", "completions"}:
        protocol = (
            "openai-compatible-responses"
            if shape == "responses"
            else "openai-compatible"
        )

    endpoint = overrides.get("api")
    if endpoint:
        # Some upstream URLs are environment-variable templates. They cannot be
        # used as literal endpoints; keep the user's configured URL instead.
        try:
            parsed = urlsplit(endpoint)
            valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        except ValueError:
            valid = False
        if not valid or "{" in endpoint:
            endpoint = None
    endpoint = endpoint or base_url
    if not overrides:
        return fallback

    if protocol == "anthropic-compatible":
        endpoint = endpoint.rstrip("/").removesuffix("/v1")
    if protocol == "gemini-compatible":
        endpoint = endpoint.rstrip("/")
        version = "v1beta"
        for suffix in ("v1beta", "v1"):
            if endpoint.endswith(f"/{suffix}"):
                endpoint = endpoint.removesuffix(f"/{suffix}")
                version = suffix
                break
        return ChatModelRoute(protocol, endpoint, version)
    return ChatModelRoute(protocol, endpoint)
