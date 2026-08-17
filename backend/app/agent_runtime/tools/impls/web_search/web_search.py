"""联网搜索工具：统一封装所有 web search provider。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.web_search.config import (
    DEFAULT_WEB_SEARCH_MAX_RESULTS,
    load_web_search_config,
)
from app.agent_runtime.tools.impls.web_search.providers import (
    get_provider,
    list_provider_names,
)
from app.agent_runtime.tools.impls.web_search.providers.base import (
    WebSearchProviderConfig,
    WebSearchResult,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session


class WebSearchInput(BaseModel):
    query: str = Field(description="检索关键词或自然语言问题")
    count: int = Field(
        default=DEFAULT_WEB_SEARCH_MAX_RESULTS,
        ge=1,
        le=20,
        description="期望返回的结果条数",
    )


class WebSearchOutput(BaseModel):
    query: str
    provider: str
    answer: str | None = None
    results: list[WebSearchResult]


@ToolRegistry.register
class WebSearchTool(AgentTool):
    name: str = "web_search"
    description: str = (
        "联网检索互联网上的公开信息，返回网页标题、链接与内容摘要。"
        "用于获取写作所需的实时信息、事实核查与资料搜集。"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = WebSearchInput

    async def _execute(
        self,
        query: str,
        count: int = DEFAULT_WEB_SEARCH_MAX_RESULTS,
    ) -> str:
        normalized_query = query.strip()
        if not normalized_query:
            raise ToolExecutionError("检索关键词不能为空")

        session = await create_session()
        try:
            config = await load_web_search_config(session)
        finally:
            await session.close()

        if not config.provider:
            raise ToolExecutionError(
                "尚未配置联网搜索，请在应用设置中配置搜索 provider 与 API Key"
                f"（可用 provider: {', '.join(list_provider_names())}）"
            )
        provider_cls = get_provider(config.provider)
        if provider_cls is None:
            raise ToolExecutionError(
                f"不支持的搜索 provider: {config.provider}"
                f"（可用: {', '.join(list_provider_names())}）"
            )

        try:
            response = await provider_cls().search(
                normalized_query,
                WebSearchProviderConfig(
                    api_key=config.api_key,
                    max_results=count,
                    extras=config.extras,
                ),
            )
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(
                f"联网搜索失败: {type(exc).__name__}: {exc}"
            ) from exc

        return WebSearchOutput(
            query=normalized_query,
            provider=config.provider,
            answer=response.answer,
            results=response.results,
        ).model_dump_json()
