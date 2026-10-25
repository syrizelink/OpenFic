"""Exercise local catalog normalization through the actual SDK request boundary."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from app.models.catalog.service import ModelProviderCatalogService
from app.models.clients.catalog_routing import resolve_chat_model_route
from app.models.clients.model_factory import ModelConfig, create_chat_model
from app.core.encryption import EncryptionService
from app.models.entities.model_provider import ModelProvider
from app.models.services.model_provider_service import ModelProviderService


@pytest.fixture
def catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service = ModelProviderCatalogService(
        bundled_snapshot_path=tmp_path / "bundled.json",
        cache_snapshot_path=tmp_path / "cache.json",
    )

    def install(payload):
        snapshot = service._build_normalized_snapshot(payload)
        service.bundled_snapshot_path.write_text(json.dumps(snapshot))
        return service

    monkeypatch.setattr(
        "app.models.catalog.service.ModelProviderCatalogService", lambda: service
    )
    return install


def _payload(provider, model, overrides=None, npm="@ai-sdk/openai-compatible"):
    return {
        provider: {
            "name": provider,
            "api": "https://opencode.ai/inference/go/openai/v1",
            "npm": npm,
            "models": {model: {"name": model, "provider": overrides}},
        }
    }


@pytest.mark.parametrize(
    ("provider", "model_id", "overrides", "expected_path", "body"),
    [
        (
            "opencode",
            "claude-haiku-5-5",
            {
                "npm": "@ai-sdk/anthropic",
                "api": "https://opencode.ai/inference/anthropic/v1/",
            },
            "/inference/anthropic/v1/messages",
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-haiku-5-5",
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        ),
        (
            "opencode-go",
            "gemini-4-argon-contributor",
            {
                "npm": "@ai-sdk/google",
                "api": "https://opencode.ai/inference/go/google/v1beta/",
            },
            "/inference/go/google/v1beta/models/gemini-4-argon-contributor:generateContent",
            {
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "ok"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 1,
                    "candidatesTokenCount": 1,
                    "totalTokenCount": 2,
                },
            },
        ),
        (
            "opencode",
            "gemini-custom",
            {"npm": "@ai-sdk/google", "api": "https://opencode.ai/zen/v1"},
            "/zen/v1/models/gemini-custom:generateContent",
            {
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "ok"}]},
                        "finishReason": "STOP",
                    }
                ]
            },
        ),
    ],
)
def test_catalog_native_requests(
    catalog, provider, model_id, overrides, expected_path, body
):
    catalog(_payload(provider, model_id, overrides))
    config = ModelConfig(
        provider, "https://opencode.ai/inference/openai/v1", "test-key", model_id
    )
    model = create_chat_model(config)
    with respx.mock as router:
        route = router.post("https://opencode.ai" + expected_path).mock(
            return_value=httpx.Response(200, json=body)
        )
        response = model.invoke("hello")
        assert response.text == "ok"
        assert route.calls[0].request.headers["x-opencode-session"] == config.session_id
    assert config.provider_type == provider
    assert config.base_url == "https://opencode.ai/inference/openai/v1"


@pytest.mark.parametrize(
    ("npm", "shape", "responses"),
    [
        ("@ai-sdk/openai", None, True),
        ("@ai-sdk/openai-compatible", None, False),
        ("@ai-sdk/openai", "completions", False),
        ("@ai-sdk/openai-compatible", "responses", True),
        ("@ai-sdk/openai", "future-shape", True),
    ],
)
def test_sdk_defaults_and_shape_override(catalog, npm, shape, responses):
    overrides = {"npm": npm, "api": "https://gateway.example/model/v1"}
    if shape:
        overrides["shape"] = shape
    catalog(_payload("gateway", "custom", overrides))
    model = create_chat_model(
        ModelConfig("gateway", "https://default.example/v1", "key", "custom")
    )
    assert bool(model.use_responses_api) is responses
    assert str(model.root_client.base_url) == "https://gateway.example/model/v1/"


def test_shape_only_inherits_provider_sdk_and_keeps_saved_url(catalog):
    catalog(_payload("gateway", "custom", {"shape": "responses"}))
    model = create_chat_model(
        ModelConfig("gateway", "https://saved.example/v1", "key", "custom")
    )
    assert model.use_responses_api is True
    assert str(model.root_client.base_url) == "https://saved.example/v1/"


@pytest.mark.parametrize(
    "provider",
    [
        "openai-compatible",
        "openai-compatible-responses",
        "gemini-compatible",
        "anthropic-compatible",
        "openai-codex",
    ],
)
def test_custom_protocols_ignore_catalog_overrides(catalog, provider):
    catalog(
        _payload(
            provider,
            "custom",
            {"npm": "@ai-sdk/google", "api": "https://wrong.example/v1beta"},
        )
    )
    route = resolve_chat_model_route(
        provider, "custom", "https://user-gateway.example/v1"
    )
    assert route.provider_type == provider
    assert route.base_url == "https://user-gateway.example/v1"


def test_unknown_sdk_keeps_existing_client_and_address(catalog):
    catalog(
        _payload(
            "gateway",
            "custom",
            {"npm": "future-sdk", "api": "https://wrong.example/v1"},
        )
    )
    route = resolve_chat_model_route("gateway", "custom", "https://saved.example/v1")
    assert route.provider_type == "gateway"
    assert route.base_url == "https://saved.example/v1"


@pytest.mark.parametrize(
    "api", ["", "https://${REGION}.example/v1", "not-a-url", "http://["]
)
def test_missing_or_template_api_keeps_saved_address(catalog, api):
    catalog(_payload("gateway", "custom", {"npm": "@ai-sdk/openai", "api": api}))
    route = resolve_chat_model_route("gateway", "custom", "https://saved.example/v1")
    assert route.base_url == "https://saved.example/v1"
    assert route.provider_type == "openai-compatible-responses"


def test_shape_without_any_sdk_metadata_uses_generic_openai_client(catalog):
    catalog(_payload("gateway", "custom", {"shape": "responses"}, npm=None))
    route = resolve_chat_model_route("gateway", "custom", "https://saved.example/v1")
    assert route.provider_type == "openai-compatible-responses"


@pytest.mark.parametrize("npm", [None, "@ai-sdk/openai-compatible"])
def test_old_catalog_preserves_native_clients_and_opencode_fallback(catalog, npm):
    catalog(_payload("opencode", "gpt-5.5", npm=npm))
    route = resolve_chat_model_route(
        "opencode", "gpt-5.5", "https://opencode.ai/zen/v1"
    )
    assert route.provider_type == "openai-compatible-responses"
    assert route.base_url == "https://opencode.ai/zen/v1"
    catalog(_payload("openai", "gpt-4o", npm=npm))
    route = resolve_chat_model_route(
        "openai", "gpt-4o", "https://user-gateway.example/v1"
    )
    assert route.provider_type == "openai"
    assert route.base_url == "https://user-gateway.example/v1"


def test_unavailable_catalog_does_not_block_legacy_calls(monkeypatch):
    def unavailable(*args):
        raise OSError("offline cache unavailable")

    monkeypatch.setattr(
        ModelProviderCatalogService, "get_model_provider_config", unavailable
    )
    assert (
        resolve_chat_model_route(
            "openai", "gpt-4o", "https://saved.example/v1"
        ).provider_type
        == "openai"
    )
    assert (
        resolve_chat_model_route(
            "opencode-go", "gemini-4-argon-contributor", "https://opencode.ai/zen/go/v1"
        ).base_url
        == "https://opencode.ai/inference/go/google"
    )


def test_responses_request_drops_unsupported_penalties(catalog):
    catalog(_payload("gateway", "custom", {"npm": "@ai-sdk/openai"}))
    model = create_chat_model(
        ModelConfig(
            "gateway",
            "https://saved.example/v1",
            "key",
            "custom",
            frequency_penalty=0.5,
            presence_penalty=0.5,
        )
    )
    payload = model._get_request_payload("hello")
    assert "frequency_penalty" not in payload
    assert "presence_penalty" not in payload


@pytest.mark.parametrize(
    ("provider", "base_url", "model_id", "expected_url", "version"),
    [
        (
            "opencode",
            "https://opencode.ai/inference/openai/v1",
            "gemini-4-argon",
            "https://opencode.ai/inference/google",
            "v1beta",
        ),
        (
            "opencode",
            "https://opencode.ai/zen/v1",
            "gemini-4-argon",
            "https://opencode.ai/zen",
            "v1",
        ),
        (
            "opencode-go",
            "https://opencode.ai/zen/go/v1",
            "gemini-4-argon-contributor",
            "https://opencode.ai/inference/go/google",
            "v1beta",
        ),
        (
            "opencode-go",
            "https://opencode.ai/inference/go/openai/v1",
            "claude-haiku-5-5",
            "https://opencode.ai/inference/go/anthropic",
            "v1beta",
        ),
        (
            "opencode",
            "https://opencode.ai/inference/openai/v1",
            "claude-haiku-5-5",
            "https://opencode.ai/inference/anthropic",
            "v1beta",
        ),
    ],
)
def test_snapshot_without_new_fields_routes_old_and_new_opencode_urls(
    catalog,
    provider,
    base_url,
    model_id,
    expected_url,
    version,
):
    service = catalog(_payload(provider, model_id))
    snapshot = json.loads(service.bundled_snapshot_path.read_text())
    for entry in snapshot["providers"]:
        entry.pop("npm", None)
        for model in entry.get("models", []):
            model.pop("provider", None)
    service.bundled_snapshot_path.write_text(json.dumps(snapshot))
    route = resolve_chat_model_route(provider, model_id, base_url)
    assert route.base_url == expected_url
    assert route.google_api_version == version


@pytest.mark.asyncio
async def test_catalog_overrides_are_exposed_and_survive_failed_refresh(catalog):
    overrides = {
        "npm": "@ai-sdk/google",
        "api": "https://opencode.ai/inference/go/google/v1beta",
    }
    service = catalog(_payload("opencode-go", "gemini-custom", overrides))
    result = await service.get_provider_models("opencode-go", "llm")
    assert result.models[0].provider == overrides
    assert result.provider.npm == "@ai-sdk/openai-compatible"
    # Simulate a successful cached catalog followed by an offline refresh.
    service.cache_snapshot_path.write_text(service.bundled_snapshot_path.read_text())
    service.source_snapshot_path = service.bundled_snapshot_path.parent / "offline.json"
    service.source_snapshot_path.write_text("invalid-json")
    await service.refresh()
    assert (
        service.get_model_provider_config("opencode-go", "gemini-custom") == overrides
    )


@pytest.mark.parametrize(
    ("provider_type", "base_url", "models_url"),
    [
        (
            "opencode",
            "https://opencode.ai/inference/openai/v1",
            "https://opencode.ai/inference/v1/models",
        ),
        (
            "opencode",
            "https://opencode.ai/inference/anthropic/v1/",
            "https://opencode.ai/inference/v1/models",
        ),
        (
            "opencode",
            "https://opencode.ai/inference/google/v1beta",
            "https://opencode.ai/inference/v1/models",
        ),
        (
            "opencode-go",
            "https://opencode.ai/inference/go/openai/v1",
            "https://opencode.ai/inference/go/v1/models",
        ),
        (
            "opencode-go",
            "https://opencode.ai/inference/go/anthropic/v1",
            "https://opencode.ai/inference/go/v1/models",
        ),
        (
            "opencode-go",
            "https://opencode.ai/inference/go/google/v1beta",
            "https://opencode.ai/inference/go/v1/models",
        ),
        ("opencode", "https://opencode.ai/zen/v1", "https://opencode.ai/zen/v1/models"),
        (
            "opencode-go",
            "https://opencode.ai/zen/go/v1",
            "https://opencode.ai/zen/go/v1/models",
        ),
        (
            "opencode",
            "https://proxy.example/inference/openai/v1",
            "https://proxy.example/inference/openai/v1/models",
        ),
        (
            "openai-compatible",
            "https://opencode.ai/inference/openai/v1",
            "https://opencode.ai/inference/openai/v1/models",
        ),
    ],
)
@pytest.mark.asyncio
async def test_model_discovery_uses_shared_endpoint(
    catalog, provider_type, base_url, models_url
):
    payload = _payload(provider_type, "test-model")
    payload[provider_type]["api"] = base_url
    catalog_service = catalog(payload)
    encryption = EncryptionService("id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ=")
    service = ModelProviderService(encryption, catalog_service=catalog_service)
    provider = ModelProvider(
        name="Test",
        provider_type=provider_type,
        url=base_url,
        api_key_encrypted=encryption.encrypt("test-key"),
    )
    with respx.mock as router:
        route = router.get(models_url).mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "test-model"}]},
            )
        )
        expected = [{"id": "test-model", "name": "test-model"}]
        assert (
            await service.validate_and_get_models(provider_type, base_url, "test-key")
            == expected
        )
        assert await service.get_available_models(provider, "llm") == expected
        assert route.call_count == 2
        assert route.calls[0].request.headers["Authorization"] == "Bearer test-key"
    assert provider.url == base_url
