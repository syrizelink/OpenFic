"""Tests for web_search tool and providers."""

import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import Response

from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.web_search.config import (
    parse_web_search_settings,
    serialize_web_search_settings,
    WebSearchSettings,
)
from app.agent_runtime.tools.impls.web_search.providers import (
    get_provider,
    list_provider_names,
)
from app.agent_runtime.tools.impls.web_search.providers.base import (
    WebSearchProviderConfig,
)
from app.core.encryption import EncryptionService
from app.settings import settings


def _make_state() -> dict:
    return {
        "session_id": "sess-1",
        "task_id": "task-1",
        "project_id": "proj-1",
        "model_config": {},
        "active_agent": None,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "message_checkpoints": [],
        "user_request": "",
        "current_revision_id": "rev-1",
    }


def _provider_config(**overrides) -> WebSearchProviderConfig:
    defaults = {"api_key": "test-key", "max_results": 8, "extras": {}}
    defaults.update(overrides)
    return WebSearchProviderConfig(**defaults)


def _make_tool():
    from app.agent_runtime.tools.impls.web_search.web_search import WebSearchTool

    return WebSearchTool(_state=_make_state())


def _encrypt(value: str) -> str:
    return EncryptionService(settings.encryption_key).encrypt(value)


class TestProviderRegistry:
    def test_all_providers_registered(self) -> None:
        assert set(list_provider_names()) == {
            "bing",
            "brave",
            "ddgs",
            "exa",
            "jina",
            "perplexity",
            "searxng",
            "serper",
            "tavily",
            "zhipu",
        }

    def test_unknown_provider_returns_none(self) -> None:
        assert get_provider("unknown") is None


class TestWebSearchConfig:
    def test_parse_missing_raw_returns_defaults(self) -> None:
        assert parse_web_search_settings(None) == WebSearchSettings()

    def test_parse_invalid_json_returns_defaults(self) -> None:
        assert parse_web_search_settings("not-json{") == WebSearchSettings()

    def test_parse_decrypts_api_key(self) -> None:
        raw = json.dumps(
            {
                "provider": "tavily",
                "api_key": _encrypt("secret-key"),
                "extras": {"doubao_model": "m1", "ignored": ""},
            }
        )
        parsed = parse_web_search_settings(raw)
        assert parsed.provider == "tavily"
        assert parsed.api_key == "secret-key"
        assert parsed.extras == {"doubao_model": "m1"}

    def test_serialize_encrypts_api_key_and_round_trips(self) -> None:
        raw = serialize_web_search_settings(
            WebSearchSettings(provider="serper", api_key="plain-key", extras={"a": "b"})
        )
        payload = json.loads(raw)
        assert payload["api_key"] != "plain-key"
        assert parse_web_search_settings(raw).api_key == "plain-key"

    def test_serialize_skips_empty_api_key(self) -> None:
        raw = serialize_web_search_settings(WebSearchSettings(provider="serper"))
        assert json.loads(raw)["api_key"] == ""


class TestWebSearchTool:
    @pytest.mark.asyncio
    async def test_unconfigured_returns_error_message(self) -> None:
        tool = _make_tool()
        with patch(
            "app.agent_runtime.tools.impls.web_search.web_search.create_session"
        ) as mock_cs:
            session = AsyncMock()
            mock_cs.return_value = session
            with patch(
                "app.agent_runtime.tools.impls.web_search.config.setting_repo.get_by_key",
                AsyncMock(return_value=None),
            ):
                result = await tool.ainvoke({"query": "hello"})

        payload = json.loads(result)
        assert "error" in payload
        assert "尚未配置" in payload["error"]
        session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unsupported_provider_returns_error(self) -> None:
        tool = _make_tool()
        raw = json.dumps({"provider": "unknown", "api_key": "", "extras": {}})
        with patch(
            "app.agent_runtime.tools.impls.web_search.web_search.create_session"
        ) as mock_cs:
            session = AsyncMock()
            mock_cs.return_value = session
            with patch(
                "app.agent_runtime.tools.impls.web_search.config.setting_repo.get_by_key",
                AsyncMock(return_value=MagicMock(value=raw)),
            ):
                result = await tool.ainvoke({"query": "hello"})

        payload = json.loads(result)
        assert "不支持的搜索 provider" in payload["error"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_serper_end_to_end(self) -> None:
        tool = _make_tool()
        raw = json.dumps(
            {"provider": "serper", "api_key": _encrypt("serper-key"), "extras": {}}
        )
        route = respx.post("https://google.serper.dev/search").mock(
            return_value=Response(
                200,
                json={
                    "organic": [
                        {"title": "t1", "link": "https://a.com", "snippet": "s1"},
                        {"title": "t2", "link": "https://b.com", "snippet": "s2"},
                    ]
                },
            )
        )
        with patch(
            "app.agent_runtime.tools.impls.web_search.web_search.create_session"
        ) as mock_cs:
            session = AsyncMock()
            mock_cs.return_value = session
            with patch(
                "app.agent_runtime.tools.impls.web_search.config.setting_repo.get_by_key",
                AsyncMock(return_value=MagicMock(value=raw)),
            ):
                result = await tool.ainvoke({"query": "量子计算", "count": 5})

        payload = json.loads(result)
        assert payload["provider"] == "serper"
        assert payload["query"] == "量子计算"
        assert payload["results"][0] == {
            "title": "t1",
            "url": "https://a.com",
            "snippet": "s1",
        }
        assert route.called
        assert route.calls[0].request.headers["x-api-key"] == "serper-key"
        assert json.loads(route.calls[0].request.read())["num"] == 5

    @pytest.mark.asyncio
    async def test_blank_query_returns_error(self) -> None:
        tool = _make_tool()
        result = await tool.ainvoke({"query": "   "})
        assert "检索关键词不能为空" in json.loads(result)["error"]


class TestHttpProviders:
    @pytest.mark.asyncio
    @respx.mock
    async def test_bing_parses_web_pages(self) -> None:
        provider = get_provider("bing")()
        route = respx.get(
            re.compile(r"^https://api\.bing\.microsoft\.com/v7\.0/search\?")
        ).mock(
            return_value=Response(
                200,
                json={
                    "webPages": {
                        "value": [
                            {
                                "name": "标题",
                                "url": "https://bing.com/r1",
                                "snippet": "摘要",
                            }
                        ]
                    }
                },
            )
        )
        response = await provider.search("q", _provider_config())
        assert route.called
        assert route.calls[0].request.headers["ocp-apim-subscription-key"] == "test-key"
        assert response.results[0].model_dump() == {
            "title": "标题",
            "url": "https://bing.com/r1",
            "snippet": "摘要",
        }

    @pytest.mark.asyncio
    @respx.mock
    async def test_brave_parses_web_results(self) -> None:
        provider = get_provider("brave")()
        route = respx.get(
            re.compile(r"^https://api\.search\.brave\.com/res/v1/web/search\?")
        ).mock(
            return_value=Response(
                200,
                json={
                    "web": {
                        "results": [
                            {"title": "t", "url": "https://u", "description": "d"}
                        ]
                    }
                },
            )
        )
        response = await provider.search("q", _provider_config())
        assert route.called
        assert route.calls[0].request.headers["x-subscription-token"] == "test-key"
        assert response.results[0].url == "https://u"

    @pytest.mark.asyncio
    @respx.mock
    async def test_searxng_requires_base_url(self) -> None:
        provider = get_provider("searxng")()
        with pytest.raises(ToolExecutionError, match="searxng_base_url"):
            await provider.search("q", _provider_config(api_key=""))

    @pytest.mark.asyncio
    @respx.mock
    async def test_searxng_parses_results_and_truncates(self) -> None:
        provider = get_provider("searxng")()
        route = respx.get(
            re.compile(r"^https://searx\.example\.com/search\?")
        ).mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {"title": f"t{i}", "url": f"https://u{i}", "content": "c"}
                        for i in range(10)
                    ]
                },
            )
        )
        response = await provider.search(
            "q",
            _provider_config(
                api_key="",
                extras={"searxng_base_url": "https://searx.example.com/"},
            ),
        )
        assert route.called
        assert len(response.results) == 8

    @pytest.mark.asyncio
    @respx.mock
    async def test_jina_parses_data_items(self) -> None:
        provider = get_provider("jina")()
        route = respx.get(re.compile(r"^https://s\.jina\.ai/\?")).mock(
            return_value=Response(
                200,
                json={
                    "code": 200,
                    "data": [
                        {"title": "t", "url": "https://u", "description": "d"},
                        {"title": "t2", "url": "https://u2", "content": "c2"},
                    ],
                },
            )
        )
        response = await provider.search("q", _provider_config())
        assert route.called
        assert route.calls[0].request.headers["authorization"] == "Bearer test-key"
        assert response.results[1].snippet == "c2"

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error_wraps_status(self) -> None:
        provider = get_provider("bing")()
        respx.get(
            re.compile(r"^https://api\.bing\.microsoft\.com/v7\.0/search\?")
        ).mock(return_value=Response(401, json={"error": "unauthorized"}))
        with pytest.raises(ToolExecutionError, match="HTTP 401"):
            await provider.search("q", _provider_config())


class TestSdkProviders:
    @pytest.mark.asyncio
    async def test_perplexity_parses_search_results(self) -> None:
        provider = get_provider("perplexity")()
        client = MagicMock()
        client.search.create = AsyncMock(
            return_value=SimpleNamespace(
                results=[
                    SimpleNamespace(
                        title="t",
                        url="https://u",
                        snippet="s",
                        source="web",
                    )
                ]
            )
        )
        client.close = AsyncMock()
        with patch(
            "app.agent_runtime.tools.impls.web_search.providers.perplexity.AsyncPerplexity",
            return_value=client,
        ) as mock_cls:
            response = await provider.search("q", _provider_config())

        mock_cls.assert_called_once_with(api_key="test-key")
        client.search.create.assert_awaited_once()
        call_kwargs = client.search.create.call_args.kwargs
        assert call_kwargs["query"] == "q"
        assert call_kwargs["max_results"] == 8
        client.close.assert_awaited_once()
        assert response.answer is None
        assert response.results[0].model_dump() == {
            "title": "t",
            "url": "https://u",
            "snippet": "s",
        }

    @pytest.mark.asyncio
    async def test_ddgs_parses_text_results(self) -> None:
        provider = get_provider("ddgs")()
        with patch(
            "app.agent_runtime.tools.impls.web_search.providers.ddgs.DDGS"
        ) as mock_cls:
            instance = mock_cls.return_value.__enter__.return_value
            instance.text.return_value = [
                {"title": "t", "href": "https://u", "body": "b"},
            ]
            response = await provider.search("q", _provider_config())

        instance.text.assert_called_once()
        assert instance.text.call_args.args == ("q",)
        assert instance.text.call_args.kwargs["max_results"] == 8
        assert response.results[0].model_dump() == {
            "title": "t",
            "url": "https://u",
            "snippet": "b",
        }

    @pytest.mark.asyncio
    async def test_tavily_parses_results_and_answer(self) -> None:
        provider = get_provider("tavily")()
        client = MagicMock()
        client.search = AsyncMock(
            return_value={
                "answer": "汇总答案",
                "results": [
                    {"title": "t", "url": "https://u", "content": "c", "score": 0.9}
                ],
            }
        )
        client.close = AsyncMock()
        with patch(
            "app.agent_runtime.tools.impls.web_search.providers.tavily.AsyncTavilyClient",
            return_value=client,
        ) as mock_cls:
            response = await provider.search("q", _provider_config())
        mock_cls.assert_called_once_with(api_key="test-key")
        client.close.assert_awaited_once()
        assert response.answer == "汇总答案"
        assert response.results[0].url == "https://u"

    @pytest.mark.asyncio
    async def test_exa_parses_highlights(self) -> None:
        provider = get_provider("exa")()
        client = MagicMock()
        client.search = AsyncMock(
            return_value=SimpleNamespace(
                results=[
                    SimpleNamespace(
                        title="t",
                        url="https://u",
                        highlights=["h1", "h2"],
                        text="",
                    ),
                    SimpleNamespace(
                        title="t2",
                        url="https://u2",
                        highlights=[],
                        text="纯文本",
                    ),
                ]
            )
        )
        with patch(
            "app.agent_runtime.tools.impls.web_search.providers.exa.AsyncExa",
            return_value=client,
        ) as mock_cls:
            response = await provider.search("q", _provider_config())
        mock_cls.assert_called_once_with(api_key="test-key")
        assert response.results[0].snippet == "h1\nh2"
        assert response.results[1].snippet == "纯文本"

    @pytest.mark.asyncio
    async def test_zhipu_parses_search_result(self) -> None:
        provider = get_provider("zhipu")()
        client = MagicMock()
        client.web_search.web_search.return_value = SimpleNamespace(
            search_result=[
                SimpleNamespace(
                    title="t",
                    link="https://u",
                    content="c",
                )
            ]
        )
        with patch(
            "app.agent_runtime.tools.impls.web_search.providers.zhipu.ZhipuAiClient",
            return_value=client,
        ) as mock_cls:
            response = await provider.search("q", _provider_config())
        mock_cls.assert_called_once_with(api_key="test-key")
        client.web_search.web_search.assert_called_once()
        call_kwargs = client.web_search.web_search.call_args.kwargs
        assert call_kwargs["search_query"] == "q"
        assert call_kwargs["search_engine"] == "search_pro"
        assert response.results[0].model_dump() == {
            "title": "t",
            "url": "https://u",
            "snippet": "c",
        }


class TestProviderKeyValidation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "name",
        ["bing", "brave", "exa", "jina", "perplexity", "serper", "tavily", "zhipu"],
    )
    async def test_providers_require_api_key(self, name: str) -> None:
        provider = get_provider(name)()
        with pytest.raises(ToolExecutionError, match="API Key"):
            await provider.search("q", _provider_config(api_key=""))
