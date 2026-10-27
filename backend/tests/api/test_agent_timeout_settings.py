import pytest
from httpx import AsyncClient
from fastapi import FastAPI

from app.storage.database import get_session

from app.agent_runtime.timeout_settings import load_agent_timeout_settings
from app.models.clients.model_factory import ModelConfig, _request_timeout, _stream_chunk_timeout


@pytest.mark.asyncio
async def test_agent_timeout_settings_persist_and_reach_model_configuration(client: AsyncClient, _test_app: FastAPI) -> None:
    values = {"llm_connect_timeout": 20, "llm_chunk_timeout": 180, "llm_request_timeout": 900}
    response = await client.put("/api/v1/settings", json=values)
    assert response.status_code == 200
    response = await client.get("/api/v1/settings")
    assert {key: response.json()[key] for key in values} == values

    session_generator = _test_app.dependency_overrides[get_session]()
    session = await anext(session_generator)
    try:
        settings = await load_agent_timeout_settings(session)
    finally:
        await session_generator.aclose()
    config = ModelConfig(provider_type="openai", base_url="", api_key="", model_id="test", **vars(settings))
    assert _request_timeout(config) == (20, 900)
    assert _stream_chunk_timeout(config) == 180


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, -1, 86401])
async def test_agent_timeout_settings_reject_out_of_range(client: AsyncClient, value: int) -> None:
    response = await client.put("/api/v1/settings", json={"llm_chunk_timeout": value})
    assert response.status_code == 422
