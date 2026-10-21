from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.models import validate_model_connection
from app.models.services.model_service import ModelService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_detail"),
    [
        (RuntimeError("Error code: 401 - Invalid API key"), "401 - Invalid API key"),
        (httpx.ReadTimeout(""), "ReadTimeout"),
    ],
)
async def test_model_validation_keeps_error_details(
    error: Exception, expected_detail: str
) -> None:
    service = AsyncMock(spec=ModelService)
    service.validate_model_connection.side_effect = error

    result = await validate_model_connection(
        "test-model", AsyncMock(spec=AsyncSession), service
    )

    assert result.success is False
    assert "模型连接验证失败" in result.message
    assert expected_detail in result.message
