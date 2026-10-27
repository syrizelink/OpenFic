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


@pytest.mark.asyncio
async def test_saved_timeouts_control_openai_model_and_stream(client: AsyncClient, _test_app: FastAPI) -> None:
    import asyncio

    from langchain_core.messages import AIMessageChunk, HumanMessage
    from openai import APITimeoutError

    from app.agent_runtime.graph.llm_invoke import LLMStreamTimeoutError
    from app.agent_runtime.graph.react_agent import _invoke_model
    from app.models.clients.model_factory import create_chat_model

    response = await client.put("/api/v1/settings", json={
        "llm_connect_timeout": 2,
        "llm_chunk_timeout": 1,
        "llm_request_timeout": 1,
    })
    assert response.status_code == 200
    session_generator = _test_app.dependency_overrides[get_session]()
    try:
        settings = await load_agent_timeout_settings(await anext(session_generator))
    finally:
        await session_generator.aclose()

    class SlowModel:
        async def astream(self, _messages):
            await asyncio.sleep(2)
            yield AIMessageChunk(content="too late")

    with pytest.raises(LLMStreamTimeoutError):
        await _invoke_model(SlowModel(), [HumanMessage(content="hello")], chunk_timeout=settings.llm_chunk_timeout)

    connected = asyncio.Event()
    handlers = set()

    async def slow_server(reader, writer):
        task = asyncio.current_task()
        handlers.add(task)
        try:
            await reader.readuntil(b"\r\n\r\n")
            connected.set()
            await asyncio.sleep(5)
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(slow_server, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        model = create_chat_model(ModelConfig(
            provider_type="openai", base_url=f"http://127.0.0.1:{port}/v1",
            api_key="test", model_id="test", **vars(settings),
        ))
        assert model.request_timeout == (2, 1)
        assert model.stream_chunk_timeout == 1
        with pytest.raises(APITimeoutError):
            await model.ainvoke([HumanMessage(content="hello")])
        assert connected.is_set()
    finally:
        server.close()
        await server.wait_closed()
        for task in list(handlers):
            task.cancel()
        await asyncio.gather(*handlers, return_exceptions=True)
