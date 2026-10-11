import httpx
import pytest
import respx

from app.api.routers.model_providers import validate_provider
from app.api.schemas.model_provider import ModelProviderValidateRequest
from app.core.encryption import EncryptionService
from app.models.services.model_provider_service import ModelProviderService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_type", ["openai-compatible", "openai-compatible-responses"]
)
@pytest.mark.parametrize(
    "base_url", ["https://gateway.example", "https://gateway.example/v1"]
)
@pytest.mark.parametrize("status_code", [401, 403, 404, 429, 500])
@respx.mock
async def test_provider_validation_keeps_http_error_details(
    provider_type: str, base_url: str, status_code: int
) -> None:
    route = respx.get(f"{base_url}/models").mock(
        return_value=httpx.Response(status_code, json={"error": "Provider error detail"})
    )
    service = ModelProviderService(
        EncryptionService("id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ=")
    )
    result = await validate_provider(
        ModelProviderValidateRequest(
            provider_type=provider_type, url=base_url, api_key="test-key"
        ),
        service,
    )

    assert result.success is False
    assert result.models == []
    assert "连接验证失败" in result.message
    assert str(status_code) in result.message
    assert "Provider error detail" in result.message
    assert f"{base_url}/models" in result.message
    assert route.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_type", ["openai-compatible", "openai-compatible-responses"]
)
@pytest.mark.parametrize(
    "error", [httpx.ReadTimeout(""), httpx.ConnectError("Connection refused")]
)
@respx.mock
async def test_provider_validation_keeps_network_error_details(
    provider_type: str, error: httpx.HTTPError
) -> None:
    respx.get("https://gateway.example/v1/models").mock(side_effect=error)
    service = ModelProviderService(
        EncryptionService("id-hEPdEELwlgep9FQhcYQtX7ow188l7WHwy65qOZGQ=")
    )

    result = await validate_provider(
        ModelProviderValidateRequest(
            provider_type=provider_type,
            url="https://gateway.example/v1",
            api_key="test-key",
        ),
        service,
    )

    assert result.success is False
    assert result.models == []
    assert type(error).__name__ in result.message
    if str(error):
        assert str(error) in result.message
