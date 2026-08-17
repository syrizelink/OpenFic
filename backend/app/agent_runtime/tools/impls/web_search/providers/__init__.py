"""联网搜索 provider 注册表。"""

from __future__ import annotations

from app.agent_runtime.tools.impls.web_search.providers.base import WebSearchProvider
from app.agent_runtime.tools.impls.web_search.providers.bing import BingProvider
from app.agent_runtime.tools.impls.web_search.providers.brave import BraveProvider
from app.agent_runtime.tools.impls.web_search.providers.ddgs import DdgsProvider
from app.agent_runtime.tools.impls.web_search.providers.exa import ExaProvider
from app.agent_runtime.tools.impls.web_search.providers.jina import JinaProvider
from app.agent_runtime.tools.impls.web_search.providers.perplexity import (
    PerplexityProvider,
)
from app.agent_runtime.tools.impls.web_search.providers.searxng import SearxngProvider
from app.agent_runtime.tools.impls.web_search.providers.serper import SerperProvider
from app.agent_runtime.tools.impls.web_search.providers.tavily import TavilyProvider
from app.agent_runtime.tools.impls.web_search.providers.zhipu import ZhipuProvider

PROVIDERS: dict[str, type[WebSearchProvider]] = {
    provider_cls.name: provider_cls
    for provider_cls in (
        BingProvider,
        BraveProvider,
        DdgsProvider,
        ExaProvider,
        JinaProvider,
        PerplexityProvider,
        SearxngProvider,
        SerperProvider,
        TavilyProvider,
        ZhipuProvider,
    )
}


def get_provider(name: str) -> type[WebSearchProvider] | None:
    return PROVIDERS.get(name)


def list_provider_names() -> tuple[str, ...]:
    return tuple(PROVIDERS)
