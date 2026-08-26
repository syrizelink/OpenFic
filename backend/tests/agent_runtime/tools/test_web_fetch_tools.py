"""Tests for the provider-independent web_fetch tool."""

from __future__ import annotations

import ipaddress
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import respx
from httpx import Response

from app.agent_runtime.tools.impls.web_fetch import service


def _make_state() -> dict:
    return {
        "session_id": "sess-1",
        "task_id": "task-1",
        "project_id": "proj-1",
    }


def _make_tool():
    from app.agent_runtime.tools.impls.web_fetch.web_fetch import WebFetchTool

    return WebFetchTool(_state=_make_state())


async def _allow_public_host(_hostname: str) -> tuple[ipaddress.IPv4Address, ...]:
    return (ipaddress.ip_address("93.184.216.34"),)


def test_allows_routable_teredo_ipv6_address() -> None:
    assert service._is_public_address(ipaddress.ip_address("2001::6ca0:a593")) is True


HTML_PAGE = """
<!doctype html>
<html lang="zh-CN">
  <head>
    <title>测试文章</title>
    <meta name="author" content="作者">
  </head>
  <body>
    <nav>导航噪声</nav>
    <article>
      <h1>测试文章</h1>
      <p>这是应该被提取的正文内容。文章正文需要足够长，才能让正文提取器区分内容区域与页面导航。</p>
      <p>第二段正文包含 <a href="/source">来源链接</a>，并且继续补充与主题相关的背景、过程和结论信息。</p>
      <p>第三段正文描述了实际发生的变化，读者可以根据这些细节理解文章的主要观点以及其中的证据。</p>
      <p>第四段正文继续说明限制条件和适用范围，避免把页面上的辅助信息误认为文章本身。</p>
    </article>
    <footer>页脚噪声</footer>
  </body>
</html>
"""


DYNAMIC_DOCUMENT_PAGE = """
<!doctype html>
<html>
  <body>
    <article id="content-container">
      <header>
        <div data-cds="Skeleton" role="status"><span class="sr-only">Loading</span></div>
        <div data-cds="Skeleton" role="status"><span class="sr-only">Loading</span></div>
      </header>
      <h1>Versions</h1>
      <!-- framework marker -->
      <p>For any given version with the Messages API, Anthropic preserves:</p>
      <ul>
        <li>Existing input parameters</li>
        <li>Existing output parameters</li>
      </ul>
      <p>However, Anthropic may do the following:</p>
      <ul>
        <li>Add additional optional inputs</li>
        <li>Add additional values to the output</li>
        <li>Change conditions for specific error types</li>
      </ul>
      <ul>
        <li><code>2023-06-01</code><ul>
          <li>New format for <a href="/streaming">streaming</a>server-sent events.</li>
          <li>Removed unnecessary <code>data: [DONE]</code>event.</li>
        </ul></li>
      </ul>
    </article>
  </body>
</html>
"""


@pytest.mark.asyncio
@respx.mock
async def test_fetches_html_and_extracts_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "resolve_public_addresses", _allow_public_host)
    route = respx.get("https://example.com/article").mock(
        return_value=Response(200, text=HTML_PAGE, headers={"content-type": "text/html"})
    )

    result = json.loads(await _make_tool().ainvoke({"url": "https://example.com/article"}))

    assert route.called
    assert result["url"] == "https://example.com/article"
    assert result["final_url"] == "https://example.com/article"
    assert result["title"] == "测试文章"
    assert "应该被提取的正文内容" in result["content"]
    assert "导航噪声" not in result["content"]
    assert result["truncated"] is False
    assert result["next_start_index"] is None


@pytest.mark.asyncio
@respx.mock
async def test_follows_valid_redirect_and_reports_final_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "resolve_public_addresses", _allow_public_host)
    first = respx.get("https://example.com/old").mock(
        return_value=Response(302, headers={"location": "/article"})
    )
    second = respx.get("https://example.com/article").mock(
        return_value=Response(200, text=HTML_PAGE, headers={"content-type": "text/html"})
    )

    result = json.loads(await _make_tool().ainvoke({"url": "https://example.com/old"}))

    assert first.called
    assert second.called
    assert result["final_url"] == "https://example.com/article"


@pytest.mark.asyncio
async def test_rejects_private_ip_without_network_request() -> None:
    result = json.loads(await _make_tool().ainvoke({"url": "http://127.0.0.1/"}))

    assert result["success"] is False
    assert result["code"] == "permission_denied"


@pytest.mark.asyncio
async def test_rejects_hostname_resolving_to_private_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service,
        "resolve_public_addresses",
        AsyncMock(return_value=(ipaddress.ip_address("192.168.1.10"),)),
    )

    result = json.loads(await _make_tool().ainvoke({"url": "https://example.com/"}))

    assert result["success"] is False
    assert result["code"] == "permission_denied"


@pytest.mark.asyncio
@respx.mock
async def test_rejects_response_over_raw_html_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "resolve_public_addresses", _allow_public_host)
    monkeypatch.setattr(service, "MAX_RAW_HTML_BYTES", 32)
    route = respx.get("https://example.com/large").mock(
        return_value=Response(
            200,
            content=b"x" * 33,
            headers={"content-type": "text/html"},
        )
    )

    result = json.loads(await _make_tool().ainvoke({"url": "https://example.com/large"}))

    assert route.called
    assert result["success"] is False
    assert result["code"] == "limit_exceeded"


@pytest.mark.asyncio
@respx.mock
async def test_returns_content_in_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "resolve_public_addresses", _allow_public_host)
    respx.get("https://example.com/article").mock(
        return_value=Response(200, text=HTML_PAGE, headers={"content-type": "text/html"})
    )

    first = json.loads(
        await _make_tool().ainvoke(
            {"url": "https://example.com/article", "max_chars": 40}
        )
    )
    second = json.loads(
        await _make_tool().ainvoke(
            {
                "url": "https://example.com/article",
                "start_index": first["next_start_index"],
                "max_chars": 40,
            }
        )
    )

    assert first["truncated"] is True
    assert first["next_start_index"] == first["start_index"] + len(first["content"])
    assert second["start_index"] == first["next_start_index"]
    assert second["content"]
    assert first["content"] != second["content"]


@pytest.mark.asyncio
@respx.mock
async def test_rejects_start_index_beyond_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "resolve_public_addresses", _allow_public_host)
    respx.get("https://example.com/article").mock(
        return_value=Response(200, text=HTML_PAGE, headers={"content-type": "text/html"})
    )

    result = json.loads(
        await _make_tool().ainvoke(
            {"url": "https://example.com/article", "start_index": 1_000_000}
        )
    )

    assert result["success"] is False
    assert result["code"] == "validation_error"


def test_removes_skeletons_and_keeps_document_lists() -> None:
    result = service.extract_html(DYNAMIC_DOCUMENT_PAGE, "https://example.com/versioning")

    assert "Loading" not in result.markdown
    assert "Existing input parameters" in result.markdown
    assert "Existing output parameters" in result.markdown
    assert "Add additional optional inputs" in result.markdown


def test_uses_recall_only_when_main_list_content_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def fake_extract_with_metadata(_html: str, *, favor_recall: bool, **_kwargs: object):
        calls.append(favor_recall)
        content = "正文" if not favor_recall else "正文\n\n- 关键文档列表项内容"
        return SimpleNamespace(
            text=content,
            title="测试页面",
            author=None,
            date=None,
            sitename=None,
            language=None,
        )

    monkeypatch.setattr(service, "extract_with_metadata", fake_extract_with_metadata)

    result = service.extract_html(
        "<article><div data-cds=\"Skeleton\">Loading</div><p>正文</p>"
        "<ul><li>关键文档列表项内容</li></ul></article>",
        "https://example.com/article",
    )

    assert calls == [False, True]
    assert "关键文档列表项内容" in result.markdown


def test_does_not_use_recall_for_regular_page_without_skeleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def fake_extract_with_metadata(_html: str, *, favor_recall: bool, **_kwargs: object):
        calls.append(favor_recall)
        return SimpleNamespace(
            text="正文",
            title="测试页面",
            author=None,
            date=None,
            sitename=None,
            language=None,
        )

    monkeypatch.setattr(service, "extract_with_metadata", fake_extract_with_metadata)

    service.extract_html(
        "<article><p>正文</p><ul><li>关键文档列表项内容</li></ul></article>",
        "https://example.com/article",
    )

    assert calls == [False]


def test_does_not_rewrite_precision_markdown_spacing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_extract_with_metadata(_html: str, *, favor_recall: bool, **_kwargs: object):
        assert favor_recall is False
        return SimpleNamespace(
            text="正文[链接](https://example.com/link)后续",
            title="测试页面",
            author=None,
            date=None,
            sitename=None,
            language=None,
        )

    monkeypatch.setattr(service, "extract_with_metadata", fake_extract_with_metadata)

    result = service.extract_html(
        "<article><p>正文</p></article>",
        "https://example.com/article",
    )

    assert result.markdown == "正文[链接](https://example.com/link)后续"


def test_separates_adjacent_inline_elements_in_document_lists() -> None:
    result = service.extract_html(DYNAMIC_DOCUMENT_PAGE, "https://example.com/versioning")

    assert "](https://example.com/streaming) server-sent events" in result.markdown
    assert "`data: [DONE]` event" in result.markdown
