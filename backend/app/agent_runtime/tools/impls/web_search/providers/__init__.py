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


BING_MARKETS = (
    "zh-CN",
    "en-US",
    "ja-JP",
    "de-DE",
    "fr-FR",
    "es-ES",
    "it-IT",
    "pt-BR",
    "ko-KR",
    "ru-RU",
)

DDGS_REGIONS = (
    "wt-wt",
    "cn-zh",
    "us-en",
    "uk-en",
    "jp-jp",
    "de-de",
    "fr-fr",
    "es-es",
    "br-pt",
)

ZHIPU_SEARCH_ENGINES = ("search_pro", "web_search_pro", "web_search_std")

PROVIDER_REQUIRES_API_KEY: frozenset[str] = frozenset(
    name for name in PROVIDERS if name not in {"ddgs", "searxng"}
)

_PROVIDER_FIELD_SPECS: dict[str, tuple[tuple[str, str, bool, tuple[str, ...]], ...]] = {
    "bing": (("bing_mkt", "select", False, BING_MARKETS),),
    "brave": (),
    "ddgs": (("ddgs_region", "select", False, DDGS_REGIONS),),
    "exa": (),
    "jina": (),
    "perplexity": (),
    "searxng": (("searxng_base_url", "text", True, ()),),
    "serper": (),
    "tavily": (),
    "zhipu": (
        ("zhipu_search_engine", "select", False, ZHIPU_SEARCH_ENGINES),
    ),
}


def list_provider_metadata() -> list[dict]:
    """按名称字母序返回 provider 元数据（requires_api_key 与扩展字段定义）。"""
    return [
        {
            "name": name,
            "requires_api_key": name in PROVIDER_REQUIRES_API_KEY,
            "fields": [
                {
                    "key": key,
                    "field_type": field_type,
                    "required": required,
                    "options": list(options),
                }
                for key, field_type, required, options in _PROVIDER_FIELD_SPECS[name]
            ],
        }
        for name in sorted(PROVIDERS)
    ]
