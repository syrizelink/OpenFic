from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.background.llm import resolver
from app.memory.summary_config import SummarySettings


def _model() -> SimpleNamespace:
    return SimpleNamespace(
        id="model-record",
        provider_id="provider-record",
        model_id="provider-model",
        temperature=None,
        top_p=None,
        top_k=None,
        min_p=None,
        top_a=None,
        max_tokens=None,
        frequency_penalty=None,
        presence_penalty=None,
        repetition_penalty=None,
    )


@pytest.mark.asyncio
async def test_summary_background_model_uses_dedicated_reasoning_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = {
        "summary_model": SimpleNamespace(value="model-record"),
        "summary_model_reasoning_effort": SimpleNamespace(value="high"),
    }
    setting_lookup = AsyncMock(side_effect=lambda _session, key: settings.get(key))
    monkeypatch.setattr(resolver.setting_repo, "get_by_key", setting_lookup)
    monkeypatch.setattr(
        resolver,
        "load_summary_settings",
        AsyncMock(return_value=SummarySettings(model_id="model-record")),
    )
    monkeypatch.setattr(resolver.model_repo, "get_by_id", AsyncMock(return_value=_model()))
    monkeypatch.setattr(
        resolver.model_provider_repo,
        "get_by_id",
        AsyncMock(
            return_value=SimpleNamespace(
                provider_type="openai",
                url="https://example.test",
                api_key_encrypted="encrypted",
            )
        ),
    )
    monkeypatch.setattr(
        resolver.EncryptionService,
        "decrypt",
        lambda _self, _value: "decrypted",
    )
    monkeypatch.setattr(
        resolver.ModelProviderService,
        "get_decrypted_custom_headers",
        lambda _self, _provider: {},
    )

    session = object()
    resolved = await resolver.resolve_background_llm(
        session,
        model_policy="summary_model",
        model_id="model-record",
    )

    assert resolved.client.config.reasoning_effort == "high"
    setting_lookup.assert_any_await(session, "summary_model_reasoning_effort")


@pytest.mark.parametrize("summary_model", ["__system_light_model__", ""])
@pytest.mark.asyncio
async def test_summary_background_model_inherits_light_model_reasoning_effort(
    monkeypatch: pytest.MonkeyPatch,
    summary_model: str,
) -> None:
    settings = {
        "summary_model": SimpleNamespace(value=summary_model),
        "light_model_reasoning_effort": SimpleNamespace(value="low"),
    }
    monkeypatch.setattr(
        resolver.setting_repo,
        "get_by_key",
        AsyncMock(side_effect=lambda _session, key: settings.get(key)),
    )
    monkeypatch.setattr(
        resolver,
        "load_summary_settings",
        AsyncMock(
            return_value=SummarySettings(
                model_id=summary_model or "__system_light_model__",
            )
        ),
    )
    monkeypatch.setattr(resolver.model_repo, "get_by_id", AsyncMock(return_value=_model()))
    monkeypatch.setattr(
        resolver.model_provider_repo,
        "get_by_id",
        AsyncMock(
            return_value=SimpleNamespace(
                provider_type="openai",
                url="https://example.test",
                api_key_encrypted="encrypted",
            )
        ),
    )
    monkeypatch.setattr(
        resolver.EncryptionService,
        "decrypt",
        lambda _self, _value: "decrypted",
    )
    monkeypatch.setattr(
        resolver.ModelProviderService,
        "get_decrypted_custom_headers",
        lambda _self, _provider: {},
    )

    resolved = await resolver.resolve_background_llm(
        object(),
        model_policy="summary_model",
        model_id="model-record",
    )

    assert resolved.client.config.reasoning_effort == "low"
