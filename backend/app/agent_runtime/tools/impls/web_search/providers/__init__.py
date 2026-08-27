"""联网搜索 provider 注册表。"""

from __future__ import annotations

from app.agent_runtime.tools.impls.web_search.providers.base import WebSearchProvider
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


ZHIPU_SEARCH_ENGINES = (
    "search_std",
    "search_pro",
    "search_pro_sogou",
    "search_pro_quark",
)

PROVIDER_REQUIRES_API_KEY: frozenset[str] = frozenset(
    name for name in PROVIDERS if name not in {"ddgs", "searxng"}
)

DDGS_BACKENDS = (
    "auto",
    "brave",
    "duckduckgo",
    "grokipedia",
    "mojeek",
    "wikipedia",
    "yahoo",
    "startpage",
)

_PROVIDER_FIELD_SPECS: dict[str, tuple[tuple[str, str, bool, tuple[str, ...]], ...]] = {
    "brave": (),
    "ddgs": (("ddgs_backend", "select", False, DDGS_BACKENDS),),
    "exa": (),
    "jina": (("jina_base_url", "text", False, ()),),
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
