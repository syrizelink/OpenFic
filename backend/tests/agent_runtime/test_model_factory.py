from app.agent_runtime.model_config import to_client_model_config
from app.models.clients.model_factory import create_chat_model, ModelConfig


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


def test_create_chat_model_anthropic_uses_openai_compatible_client():
    config = ModelConfig(
        provider_type="anthropic",
        base_url="",
        api_key="sk-ant-test",
        model_id="claude-sonnet-4-6",
    )
    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)


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


def test_create_chat_model_disables_retries_for_google_genai():
    config = ModelConfig(
        provider_type="google-genai",
        base_url="",
        api_key="sk-google-test",
        model_id="gemini-2.0-flash",
    )
    model = create_chat_model(config)
    assert model.max_retries == 0


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


def test_create_chat_model_forces_openai_compatible_for_non_builtin_provider():
    config = ModelConfig(
        provider_type="anthropic",
        base_url="https://api.anthropic.com",
        api_key="sk-ant-test",
        model_id="claude-sonnet-4-6",
        use_openai_compatible=True,
    )

    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)
    assert model.openai_api_base == "https://api.anthropic.com"


def test_create_chat_model_deepseek_uses_openai_compatible_client():
    config = ModelConfig(
        provider_type="deepseek",
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        model_id="deepseek-v4-flash",
        deepseek_reasoning_effort="high",
        deepseek_thinking_type="enabled",
    )
    model = create_chat_model(config)
    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)


def test_create_chat_model_openrouter_uses_openai_compatible_client():
    config = ModelConfig(
        provider_type="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-test",
        model_id="openai/gpt-4o-mini",
    )

    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)


def test_create_chat_model_groq_uses_openai_compatible_client():
    config = ModelConfig(
        provider_type="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk_test",
        model_id="llama-3.3-70b-versatile",
    )

    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)


def test_create_chat_model_cohere_uses_openai_compatible_client():
    config = ModelConfig(
        provider_type="cohere",
        base_url="https://api.cohere.com/v2",
        api_key="cohere-test",
        model_id="command-a-03-2025",
    )

    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)


def test_create_chat_model_ollama_uses_openai_compatible_client():
    config = ModelConfig(
        provider_type="ollama",
        base_url="http://localhost:11434",
        api_key="ollama-test",
        model_id="llama3.2",
    )

    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)


def test_create_chat_model_amazon_nova_uses_openai_compatible_client():
    config = ModelConfig(
        provider_type="amazon-nova",
        base_url="https://api.nova.amazon.com/v1",
        api_key="nova-test",
        model_id="nova-2-pro-v1",
    )

    model = create_chat_model(config)

    from langchain_openai import ChatOpenAI

    assert isinstance(model, ChatOpenAI)
