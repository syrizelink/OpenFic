import tiktoken.load
import tiktoken.registry
import pytest

from app.agent_runtime.model_config import to_client_model_config, without_api_key
from app.models.clients.model_factory import create_chat_model, ModelConfig


_ANTHROPIC_COMPATIBLE_PROVIDER_TYPES = [
    "freemodel",
    "minimax",
    "minimax-cn",
    "minimax-coding-plan",
    "minimax-cn-coding-plan",
    "subconscious",
    "thinkingmachines",
]


def test_to_client_model_config_excludes_internal_model_record_id():
    config = to_client_model_config(
        {
            "model_record_id": "model-record-1",
            "provider_type": "openai-compatible",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model_id": "gpt-4o",
        }
    )

    model = create_chat_model(ModelConfig(**config))

    assert model.model_name == "gpt-4o"


def test_without_api_key_removes_custom_headers_from_persisted_config():
    persisted = without_api_key(
        {
            "api_key": "sk-test",
            "custom_headers": {"X-Provider-Token": "custom-token"},
        }
    )

    assert persisted == {}


def test_create_chat_model_openai_returns_chat_openai():
    config = ModelConfig(
        provider_type="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model_id="gpt-4o",
    )
    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-4o"
    assert model.stream_chunk_timeout == 120.0
    assert model.request_timeout == (10.0, 600.0)


def test_create_chat_model_openai_codex_uses_dynamic_provider_reference():
    from app.models.clients.openai_codex import OpenAICodexChatModel

    model = create_chat_model(
        ModelConfig(
            provider_type="openai-codex",
            base_url="https://api.openai.com/v1",
            api_key="",
            provider_id="provider-1",
            model_id="gpt-visible",
        )
    )

    assert isinstance(model, OpenAICodexChatModel)
    assert model.provider_id == "provider-1"
    assert model.api_key == ""


def test_create_chat_model_anthropic_uses_native_client():
    config = ModelConfig(
        provider_type="anthropic",
        base_url="",
        api_key="sk-ant-test",
        model_id="claude-sonnet-4-6",
    )
    model = create_chat_model(config)

    from langchain_anthropic import ChatAnthropic

    assert isinstance(model, ChatAnthropic)


def test_create_chat_model_anthropic_compatible_uses_anthropic_client_with_custom_url():
    config = ModelConfig(
        provider_type="anthropic-compatible",
        base_url="https://gateway.example/v1",
        api_key="test-key",
        model_id="custom-claude",
        reasoning_effort="high",
    )

    model = create_chat_model(config)

    from langchain_anthropic import ChatAnthropic

    assert isinstance(model, ChatAnthropic)
    assert model.anthropic_api_url == "https://gateway.example/v1"
    assert model.effort == "high"
    assert model.max_retries == 0


@pytest.mark.parametrize("provider_type", _ANTHROPIC_COMPATIBLE_PROVIDER_TYPES)
def test_create_chat_model_uses_anthropic_client_for_anthropic_catalog_provider(
    provider_type: str,
):
    model = create_chat_model(
        ModelConfig(
            provider_type=provider_type,
            base_url="https://gateway.example/v1",
            api_key="test-key",
            model_id="custom-model",
        )
    )

    from langchain_anthropic import ChatAnthropic

    assert isinstance(model, ChatAnthropic)


def test_create_chat_model_gemini_compatible_uses_custom_native_client():
    config = ModelConfig(
        provider_type="gemini-compatible",
        base_url="https://gateway.example/gemini",
        api_key="test-key",
        model_id="gemini-custom",
        custom_headers={"X-Provider-Token": "custom-token"},
        reasoning_effort="max",
    )

    model = create_chat_model(config)

    from langchain_google_genai import ChatGoogleGenerativeAI

    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.base_url == {"api_endpoint": "https://gateway.example/gemini"}
    assert model.api_version == "v1beta"
    assert model.additional_headers["X-Provider-Token"] == "custom-token"
    assert model.additional_headers["User-Agent"].startswith("OpenFic/")
    assert model.thinking_level == "high"
    assert model.max_retries == 0


def test_create_chat_model_custom_providers_send_custom_headers():
    openai_model = create_chat_model(
        ModelConfig(
            provider_type="openai-compatible",
            base_url="https://gateway.example/v1",
            api_key="test-key",
            model_id="custom-model",
            custom_headers={"X-Provider-Token": "custom-token"},
        )
    )
    anthropic_model = create_chat_model(
        ModelConfig(
            provider_type="anthropic-compatible",
            base_url="https://gateway.example/v1",
            api_key="test-key",
            model_id="custom-claude",
            custom_headers={"X-Provider-Token": "custom-token"},
        )
    )

    assert openai_model.default_headers["X-Provider-Token"] == "custom-token"
    assert anthropic_model.default_headers["X-Provider-Token"] == "custom-token"
    assert openai_model.default_headers["User-Agent"].startswith("OpenFic/")
    assert anthropic_model.default_headers["User-Agent"].startswith("OpenFic/")


def test_create_chat_model_adds_versioned_application_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "app_name", "OpenFic")
    monkeypatch.setattr(settings, "app_version", "0.11.1")

    model = create_chat_model(
        ModelConfig(
            provider_type="opencode",
            base_url="https://opencode.example/v1",
            api_key="test-key",
            model_id="custom-model",
            session_id="agent-session-1",
            custom_headers={"X-Provider-Token": "custom-token"},
        )
    )

    assert model.default_headers["User-Agent"] == "OpenFic/0.11.1"
    assert model.default_headers["X-Provider-Token"] == "custom-token"


@pytest.mark.parametrize("provider_type", ["opencode", "opencode-go"])
def test_create_chat_model_adds_opencode_session_header(provider_type: str) -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type=provider_type,
            base_url="https://opencode.example/v1",
            api_key="test-key",
            model_id="test-model",
            session_id="agent-session-1",
        )
    )

    assert model.default_headers["x-opencode-session"] == "agent-session-1"


def test_create_chat_model_adds_opencode_headers_for_openai_compatible_endpoint() -> None:
    from app.settings import settings

    model = create_chat_model(
        ModelConfig(
            provider_type="openai-compatible",
            base_url="https://opencode.ai/zen/go/v1",
            api_key="test-key",
            model_id="test-model",
            session_id="agent-session-1",
        )
    )

    assert model.default_headers["User-Agent"] == f"{settings.app_name}/{settings.app_version}"
    assert model.default_headers["x-opencode-session"] == "agent-session-1"


def test_create_chat_model_generates_opencode_session_when_not_provided() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="openai-compatible",
            base_url="https://opencode.ai/zen/go/v1",
            api_key="test-key",
            model_id="test-model",
        )
    )

    assert model.default_headers["x-opencode-session"]


@pytest.mark.parametrize(
    ("provider_type", "base_url"),
    [
        ("opencode", "https://opencode.ai/zen/v1"),
        ("opencode-go", "https://opencode.ai/zen/go/v1"),
    ],
)
@pytest.mark.parametrize("model_id", ["gpt-6-luna", "grok-4.6", "muse-spark-1.3"])
def test_create_chat_model_routes_opencode_responses_models_to_responses_api(
    provider_type: str,
    base_url: str,
    model_id: str,
) -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type=provider_type,
            base_url=base_url,
            api_key="test-key",
            model_id=model_id,
            session_id="agent-session-1",
        )
    )

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)
    assert model.use_responses_api is True
    assert str(model.root_client.base_url) == f"{base_url}/"
    assert model.default_headers["x-opencode-session"] == "agent-session-1"


def test_create_chat_model_keeps_generated_opencode_session_on_original_config() -> None:
    config = ModelConfig(
        provider_type="opencode",
        base_url="https://opencode.ai/zen/v1",
        api_key="test-key",
        model_id="grok-4.6",
    )

    model = create_chat_model(config)

    assert config.session_id
    assert model.default_headers["x-opencode-session"] == config.session_id


@pytest.mark.parametrize("provider_type", ["opencode", "opencode-go"])
def test_create_chat_model_keeps_chat_completions_for_other_opencode_models(
    provider_type: str,
) -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type=provider_type,
            base_url="https://opencode.ai/zen/v1",
            api_key="test-key",
            model_id="deepseek-v4-pro",
        )
    )

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)
    assert not model.use_responses_api


def test_create_chat_model_routes_opencode_zen_gemini_to_native_v1_endpoint() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="opencode",
            base_url="https://opencode.ai/zen/v1",
            api_key="test-key",
            model_id="gemini-3.8-flash",
            session_id="agent-session-1",
            reasoning_effort="max",
        )
    )

    from langchain_google_genai import ChatGoogleGenerativeAI

    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.base_url == {"api_endpoint": "https://opencode.ai/zen"}
    assert model.api_version == "v1"
    assert model.additional_headers["x-opencode-session"] == "agent-session-1"
    assert model.thinking_level == "high"
    assert model.max_retries == 0


def test_create_chat_model_routes_opencode_go_gemini_to_native_client() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="opencode-go",
            base_url="https://opencode.ai/zen/go/v1",
            api_key="test-key",
            model_id="gemini-3.8-flash",
        )
    )

    from langchain_google_genai import ChatGoogleGenerativeAI

    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.base_url == {"api_endpoint": "https://opencode.ai/inference/go/google"}
    assert model.api_version == "v1beta"


@pytest.mark.parametrize(
    ("provider_type", "base_url", "expected_base_url"),
    [
        ("opencode", "https://opencode.ai/zen/v1", "https://opencode.ai/zen"),
        ("opencode-go", "https://opencode.ai/zen/go/v1/", "https://opencode.ai/zen/go"),
    ],
)
def test_create_chat_model_routes_opencode_claude_models_to_anthropic_messages(
    provider_type: str,
    base_url: str,
    expected_base_url: str,
) -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type=provider_type,
            base_url=base_url,
            api_key="test-key",
            model_id="claude-haiku-5-5",
            session_id="agent-session-1",
        )
    )

    from langchain_anthropic import ChatAnthropic

    assert isinstance(model, ChatAnthropic)
    assert model.anthropic_api_url == expected_base_url
    assert model.default_headers["x-opencode-session"] == "agent-session-1"


def test_create_chat_model_does_not_reroute_user_selected_provider_type() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="openai-compatible",
            base_url="https://opencode.ai/zen/v1",
            api_key="test-key",
            model_id="grok-4.6",
        )
    )

    assert not model.use_responses_api


def test_create_chat_model_does_not_add_opencode_header_to_other_providers() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="openai-compatible",
            base_url="https://gateway.example/v1",
            api_key="test-key",
            model_id="test-model",
            session_id="agent-session-1",
        )
    )

    assert "x-opencode-session" not in model.default_headers


def test_create_chat_model_adds_application_user_agent_to_non_opencode_provider() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="openai-compatible",
            base_url="https://gateway.example/v1",
            api_key="test-key",
            model_id="test-model",
        )
    )

    assert model.default_headers["User-Agent"].startswith("OpenFic/")


def test_create_chat_model_with_temperature():
    config = ModelConfig(
        provider_type="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model_id="gpt-4o",
        temperature=0.7,
    )
    model = create_chat_model(config)
    assert model.temperature == 0.7


def test_create_chat_model_omits_default_advanced_params_from_request():
    model = create_chat_model(
        ModelConfig(
            provider_type="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model_id="gpt-4o",
            temperature=1.0,
            top_p=1.0,
            top_k=0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            repetition_penalty=1.0,
            min_p=0.0,
            top_a=0.0,
        )
    )

    assert model._default_params == {  # type: ignore[attr-defined]
        "model": "gpt-4o",
        "stream": False,
    }


def test_create_chat_model_sends_non_default_advanced_params():
    model = create_chat_model(
        ModelConfig(
            provider_type="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model_id="gpt-4o",
            temperature=0.7,
            top_p=0.9,
            top_k=32,
            frequency_penalty=0.2,
            presence_penalty=0.1,
            repetition_penalty=1.1,
            min_p=0.05,
            top_a=0.1,
            reasoning_effort="high",
        )
    )

    assert model._default_params == {  # type: ignore[attr-defined]
        "model": "gpt-4o",
        "stream": False,
        "temperature": 0.7,
        "top_p": 0.9,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.1,
        "reasoning_effort": "high",
        "extra_body": {
            "top_k": 32,
            "repetition_penalty": 1.1,
            "min_p": 0.05,
            "top_a": 0.1,
        },
    }


def test_create_chat_model_omits_auto_reasoning_effort():
    model = create_chat_model(
        ModelConfig(
            provider_type="openai-compatible",
            base_url="https://custom.api/v1",
            api_key="sk-test",
            model_id="new-reasoning-model",
            reasoning_effort="auto",
        )
    )

    assert model._default_params == {  # type: ignore[attr-defined]
        "model": "new-reasoning-model",
        "stream": False,
    }


def test_create_chat_model_deepseek_omits_auto_reasoning_effort():
    model = create_chat_model(
        ModelConfig(
            provider_type="deepseek",
            base_url="https://api.deepseek.com",
            api_key="sk-test",
            model_id="deepseek-reasoner",
            reasoning_effort="auto",
        )
    )

    assert "reasoning_effort" not in model._default_params  # type: ignore[attr-defined]


def test_create_chat_model_maps_anthropic_reasoning_effort():
    model = create_chat_model(
        ModelConfig(
            provider_type="anthropic",
            base_url="",
            api_key="sk-ant-test",
            model_id="claude-sonnet-4-6",
            reasoning_effort="xhigh",
        )
    )

    assert model.effort == "xhigh"


def test_create_chat_model_maps_google_reasoning_effort():
    model = create_chat_model(
        ModelConfig(
            provider_type="google-genai",
            base_url="",
            api_key="sk-google-test",
            model_id="gemini-3-pro-preview",
            reasoning_effort="max",
        )
    )

    assert model.thinking_level == "high"


def test_create_chat_model_maps_openrouter_reasoning_effort():
    model = create_chat_model(
        ModelConfig(
            provider_type="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-test",
            model_id="openai/gpt-5.2",
            reasoning_effort="high",
        )
    )

    assert model._default_params["reasoning"] == {"effort": "high"}  # type: ignore[attr-defined]


def test_create_chat_model_maps_groq_reasoning_effort():
    model = create_chat_model(
        ModelConfig(
            provider_type="groq",
            base_url="https://api.groq.com/openai/v1",
            api_key="gsk_test",
            model_id="openai/gpt-oss-120b",
            reasoning_effort="max",
        )
    )

    assert model._default_params["reasoning_effort"] == "high"  # type: ignore[attr-defined]


def test_create_chat_model_maps_cohere_reasoning_effort():
    model = create_chat_model(
        ModelConfig(
            provider_type="cohere",
            base_url="https://api.cohere.com/v2",
            api_key="cohere-test",
            model_id="command-a-reasoning-08-2025",
            reasoning_effort="medium",
        )
    )

    assert model._default_params["thinking"] == {  # type: ignore[attr-defined]
        "type": "enabled",
        "token_budget": 4096,
    }


def test_create_chat_model_maps_amazon_nova_reasoning_effort():
    model = create_chat_model(
        ModelConfig(
            provider_type="amazon-nova",
            base_url="https://api.nova.amazon.com/v1",
            api_key="nova-test",
            model_id="nova-2-pro-v1",
            reasoning_effort="max",
        )
    )

    assert model._default_params["reasoning_effort"] == "high"  # type: ignore[attr-defined]


def test_create_chat_model_passes_reasoning_effort_to_mistral():
    mistral_model = create_chat_model(
        ModelConfig(
            provider_type="mistral",
            base_url="https://api.mistral.ai",
            api_key="sk-mistral-test",
            model_id="magistral-medium",
            reasoning_effort="high",
        )
    )
    assert mistral_model._default_params["reasoning_effort"] == "high"  # type: ignore[attr-defined]


def test_create_chat_model_enables_nvidia_thinking_mode():
    nvidia_model = create_chat_model(
        ModelConfig(
            provider_type="nvidia-ai-endpoints",
            base_url="https://integrate.api.nvidia.com/v1",
            api_key="nvapi-test",
            model_id="deepseek-ai/deepseek-v4-pro",
            reasoning_effort="high",
        )
    )

    assert getattr(nvidia_model, "kwargs") == {"thinking_mode": True}
    bound_model = getattr(nvidia_model, "bound")
    payload = bound_model._get_payload(  # type: ignore[no-untyped-call]
        [{"role": "user", "content": "test"}],
        stop=None,
        **getattr(nvidia_model, "kwargs"),
    )
    assert payload["chat_template_kwargs"] == {"thinking": True}


def test_create_chat_model_disables_provider_internal_retries_for_openai_like_models():
    config = ModelConfig(
        provider_type="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model_id="gpt-4o",
    )
    model = create_chat_model(config)
    assert model.max_retries == 0


def test_create_chat_model_disables_provider_internal_retries_for_anthropic():
    config = ModelConfig(
        provider_type="anthropic",
        base_url="",
        api_key="sk-ant-test",
        model_id="claude-sonnet-4-6",
    )
    model = create_chat_model(config)
    assert model.max_retries == 0


def test_create_chat_model_disables_provider_internal_retries_for_deepseek():
    config = ModelConfig(
        provider_type="deepseek",
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        model_id="deepseek-v4-flash",
    )
    model = create_chat_model(config)
    assert model.max_retries == 0


def test_create_chat_model_disables_provider_internal_retries_for_mistral():
    config = ModelConfig(
        provider_type="mistral",
        base_url="https://api.mistral.ai",
        api_key="sk-mistral-test",
        model_id="mistral-small",
    )
    model = create_chat_model(config)
    assert model.max_retries == 0


def test_create_chat_model_configures_google_genai_retries():
    config = ModelConfig(
        provider_type="google-genai",
        base_url="",
        api_key="sk-google-test",
        model_id="gemini-2.0-flash",
    )
    model = create_chat_model(config)
    assert model.max_retries == 1


def test_create_chat_model_unknown_provider_falls_back_to_openai():
    config = ModelConfig(
        provider_type="some-unknown-provider",
        base_url="https://custom.api/v1",
        api_key="sk-test",
        model_id="custom-model",
    )
    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)


def test_create_chat_model_uses_native_client_for_configured_provider():
    config = ModelConfig(
        provider_type="anthropic",
        base_url="https://api.anthropic.com",
        api_key="sk-ant-test",
        model_id="claude-sonnet-4-6",
    )

    model = create_chat_model(config)

    from langchain_anthropic import ChatAnthropic

    assert isinstance(model, ChatAnthropic)
    assert model.anthropic_api_url == "https://api.anthropic.com"


def test_create_chat_model_deepseek_uses_native_client(monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_chunk_timeout", 77.0)
    config = ModelConfig(
        provider_type="deepseek",
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        model_id="deepseek-v4-flash",
    )
    model = create_chat_model(config)
    from langchain_deepseek import ChatDeepSeek

    assert isinstance(model, ChatDeepSeek)
    assert model.stream_chunk_timeout == 77.0


def test_create_chat_model_openrouter_uses_native_client(monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_request_timeout", 600.0)
    config = ModelConfig(
        provider_type="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-test",
        model_id="openai/gpt-4o-mini",
    )

    model = create_chat_model(config)

    from langchain_openrouter import ChatOpenRouter

    assert isinstance(model, ChatOpenRouter)
    assert model.request_timeout == 600000


def test_create_chat_model_groq_uses_native_client():
    config = ModelConfig(
        provider_type="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk_test",
        model_id="llama-3.3-70b-versatile",
    )

    model = create_chat_model(config)

    from langchain_groq import ChatGroq

    assert isinstance(model, ChatGroq)


def test_create_chat_model_cohere_uses_native_client():
    config = ModelConfig(
        provider_type="cohere",
        base_url="https://api.cohere.com/v2",
        api_key="cohere-test",
        model_id="command-a-03-2025",
    )

    model = create_chat_model(config)

    from langchain_cohere import ChatCohere

    assert isinstance(model, ChatCohere)


def test_create_chat_model_ollama_uses_openai_compatible_client():
    config = ModelConfig(
        provider_type="ollama",
        base_url="https://ollama.com/v1",
        api_key="ollama-test",
        model_id="glm-5",
    )

    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)
    assert str(model.root_client.base_url) == "https://ollama.com/v1/"


def test_create_chat_model_amazon_nova_uses_native_client():
    config = ModelConfig(
        provider_type="amazon-nova",
        base_url="https://api.nova.amazon.com/v1",
        api_key="nova-test",
        model_id="nova-2-pro-v1",
    )

    model = create_chat_model(config)

    from langchain_amazon_nova import ChatAmazonNova

    assert isinstance(model, ChatAmazonNova)


def test_create_chat_model_openai_compatible_enables_stream_usage_for_custom_base_url():
    config = ModelConfig(
        provider_type="openai-compatible",
        base_url="https://custom.api/v1",
        api_key="sk-test",
        model_id="custom-model",
    )
    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)
    assert model.stream_usage is True


def test_create_chat_model_openai_responses_compatible_uses_responses_api():
    config = ModelConfig(
        provider_type="openai-compatible-responses",
        base_url="https://gateway.example/v1",
        api_key="sk-test",
        model_id="responses-model",
    )
    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)
    assert model.use_responses_api is True
    assert str(model.root_client.base_url) == "https://gateway.example/v1/"


def test_create_chat_model_deepseek_enables_stream_usage():
    config = ModelConfig(
        provider_type="deepseek",
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        model_id="deepseek-v4-flash",
    )
    model = create_chat_model(config)

    from langchain_deepseek import ChatDeepSeek

    assert isinstance(model, ChatDeepSeek)
    assert model.stream_usage is True


def test_create_chat_model_deepseek_uses_bundled_tiktoken_encoding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path / "tiktoken-cache"))
    monkeypatch.setattr(tiktoken.registry, "ENCODINGS", {})

    def fail_if_network_requested(_: str) -> bytes:
        raise AssertionError(
            "LangChain token counting must not request network resources"
        )

    monkeypatch.setattr(tiktoken.load, "read_file", fail_if_network_requested)
    model = create_chat_model(
        ModelConfig(
            provider_type="deepseek",
            base_url="https://api.deepseek.com",
            api_key="sk-test",
            model_id="deepseek-chat",
        )
    )

    assert model.get_token_ids("OpenFic 离线 token 测试")


def _openai_compatible_model():
    return create_chat_model(
        ModelConfig(
            provider_type="openai-compatible",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key="test-key",
            model_id="gemini-3.5-flash",
        )
    )


_THOUGHT_SIGNATURE = {"google": {"thought_signature": "sig-abc-123"}}


def _payload_assistant_tool_calls(model, ai_message, tool_call_id):
    from langchain_core.messages import HumanMessage, ToolMessage

    payload = model._get_request_payload(
        [
            HumanMessage(content="weather in Paris?"),
            ai_message,
            ToolMessage(content="sunny", tool_call_id=tool_call_id),
        ]
    )
    return payload["messages"][1]["tool_calls"]


def test_openai_compatible_streaming_tool_call_extra_content_round_trips() -> None:
    from langchain_core.messages import AIMessage, AIMessageChunk

    model = _openai_compatible_model()
    first = model._convert_chunk_to_generation_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "function-call-1",
                                "type": "function",
                                "function": {"name": "get_weather", "arguments": ""},
                                "extra_content": _THOUGHT_SIGNATURE,
                            }
                        ],
                    },
                    "finish_reason": None,
                }
            ],
            "model": "gemini-3.5-flash",
        },
        AIMessageChunk,
        None,
    )
    second = model._convert_chunk_to_generation_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {
                                    "name": None,
                                    "arguments": '{"city": "Paris"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "model": "gemini-3.5-flash",
        },
        AIMessageChunk,
        None,
    )
    assert first is not None and second is not None
    merged = first.message + second.message
    ai_message = AIMessage(
        content=merged.content,
        additional_kwargs=dict(merged.additional_kwargs),
        tool_calls=merged.tool_calls,
    )

    assert ai_message.additional_kwargs["tool_call_extra_content"] == {
        "function-call-1": _THOUGHT_SIGNATURE
    }
    tool_calls = _payload_assistant_tool_calls(model, ai_message, "function-call-1")
    assert tool_calls[0]["extra_content"] == _THOUGHT_SIGNATURE


def test_openai_compatible_non_streaming_tool_call_extra_content_round_trips() -> None:
    model = _openai_compatible_model()
    result = model._create_chat_result(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "function-call-9",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"city": "Paris"}',
                                },
                                "extra_content": _THOUGHT_SIGNATURE,
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "model": "gemini-3.5-flash",
        }
    )

    ai_message = result.generations[0].message
    assert ai_message.additional_kwargs["tool_call_extra_content"] == {
        "function-call-9": _THOUGHT_SIGNATURE
    }
    tool_calls = _payload_assistant_tool_calls(model, ai_message, "function-call-9")
    assert tool_calls[0]["extra_content"] == _THOUGHT_SIGNATURE


def test_openai_compatible_multiple_tool_calls_keep_their_own_extra_content() -> None:
    model = _openai_compatible_model()
    result = model._create_chat_result(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-a",
                                "type": "function",
                                "function": {"name": "get_weather", "arguments": "{}"},
                                "extra_content": {"google": {"thought_signature": "a"}},
                            },
                            {
                                "id": "call-b",
                                "type": "function",
                                "function": {"name": "get_time", "arguments": "{}"},
                            },
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "model": "gemini-3.5-flash",
        }
    )

    ai_message = result.generations[0].message
    tool_calls = _payload_assistant_tool_calls(model, ai_message, "call-a")
    assert tool_calls[0]["extra_content"] == {"google": {"thought_signature": "a"}}
    assert "extra_content" not in tool_calls[1]


def test_openai_compatible_tool_call_without_extra_content_is_unchanged() -> None:
    from langchain_core.messages import AIMessageChunk

    model = _openai_compatible_model()
    generation = model._convert_chunk_to_generation_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-plain",
                                "type": "function",
                                "function": {"name": "get_weather", "arguments": "{}"},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "model": "gpt-4o",
        },
        AIMessageChunk,
        None,
    )
    assert generation is not None
    assert "tool_call_extra_content" not in generation.message.additional_kwargs

    from langchain_core.messages import AIMessage

    ai_message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_weather",
                "args": {},
                "id": "call-plain",
                "type": "tool_call",
            }
        ],
    )
    tool_calls = _payload_assistant_tool_calls(model, ai_message, "call-plain")
    assert tool_calls == [
        {
            "type": "function",
            "id": "call-plain",
            "function": {"name": "get_weather", "arguments": "{}"},
        }
    ]


def _non_streaming_tool_call_message(model, extra_content):
    result = model._create_chat_result(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-gated",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"city": "Paris"}',
                                },
                                "extra_content": extra_content,
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "model": "gemini-3.5-flash",
        }
    )
    return result.generations[0].message


def test_openai_compatible_non_google_base_url_does_not_record_extra_content() -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type="openai-compatible",
            base_url="https://api.example.com/v1",
            api_key="test-key",
            model_id="gemini-3.5-flash",
        )
    )
    ai_message = _non_streaming_tool_call_message(model, _THOUGHT_SIGNATURE)
    assert "tool_call_extra_content" not in ai_message.additional_kwargs
    tool_calls = _payload_assistant_tool_calls(model, ai_message, "call-gated")
    assert "extra_content" not in tool_calls[0]


def test_openai_compatible_google_base_url_without_thought_signature_does_not_record() -> None:
    model = _openai_compatible_model()
    for extra_content in (
        {},
        {"google": {}},
        {"google": {"thought_signature": ""}},
        {"other": {"thought_signature": "sig-x"}},
    ):
        ai_message = _non_streaming_tool_call_message(model, extra_content)
        assert "tool_call_extra_content" not in ai_message.additional_kwargs
        tool_calls = _payload_assistant_tool_calls(model, ai_message, "call-gated")
        assert "extra_content" not in tool_calls[0]


def test_openai_compatible_non_google_base_url_streaming_does_not_record_extra_content() -> None:
    from langchain_core.messages import AIMessageChunk

    model = create_chat_model(
        ModelConfig(
            provider_type="openai-compatible",
            base_url="https://api.example.com/v1",
            api_key="test-key",
            model_id="gemini-3.5-flash",
        )
    )
    generation = model._convert_chunk_to_generation_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-gated",
                                "type": "function",
                                "function": {"name": "get_weather", "arguments": "{}"},
                                "extra_content": _THOUGHT_SIGNATURE,
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "model": "gemini-3.5-flash",
        },
        AIMessageChunk,
        None,
    )
    assert generation is not None
    assert "tool_call_extra_content" not in generation.message.additional_kwargs


@pytest.mark.parametrize(
    "provider_type,base_url,model_id",
    [
        ("openai", "https://api.openai.com/v1", "gpt-4o"),
        ("huggingface", "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-3.5-flash"),
    ],
)
def test_non_openai_compatible_provider_does_not_record_extra_content(
    provider_type, base_url, model_id
) -> None:
    model = create_chat_model(
        ModelConfig(
            provider_type=provider_type,
            base_url=base_url,
            api_key="test-key",
            model_id=model_id,
        )
    )
    ai_message = _non_streaming_tool_call_message(model, _THOUGHT_SIGNATURE)
    assert "tool_call_extra_content" not in ai_message.additional_kwargs
    tool_calls = _payload_assistant_tool_calls(model, ai_message, "call-gated")
    assert "extra_content" not in tool_calls[0]
