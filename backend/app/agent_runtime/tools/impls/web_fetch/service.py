"""异步下载静态网页并使用 Trafilatura 提取正文。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from charset_normalizer import from_bytes
from lxml import html as lxml_html
from trafilatura import extract_with_metadata

from app.agent_runtime.tools.errors import ToolExecutionError

DEFAULT_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DEFAULT_USER_AGENT = "OpenFic-WebFetch/1.0"
FALLBACK_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MAX_RAW_HTML_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
ALLOWED_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})
TEREDO_NETWORK = ipaddress.ip_network("2001::/32")
INLINE_ELEMENTS = frozenset(
    {"a", "abbr", "b", "code", "em", "i", "kbd", "mark", "q", "s", "small", "span", "strong"}
)
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]\n]+\]\([^\)\n]+\)")
INLINE_CODE_PATTERN = re.compile(r"(?<!`)`[^`\n]+`(?!`)")


@dataclass(frozen=True)
class FetchedPage:
    final_url: str
    status_code: int
    content_type: str
    html: str
    icon_url: str | None


@dataclass(frozen=True)
class ExtractedPage:
    markdown: str
    title: str
    author: str | None
    date: str | None
    site_name: str | None
    language: str | None


def normalize_url(value: str) -> str:
    normalized = value.strip()
    try:
        parts = urlsplit(normalized)
        port = parts.port
    except ValueError as exc:
        raise ToolExecutionError("URL 格式无效", code="validation_error") from exc

    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ToolExecutionError(
            "只支持 http 和 https URL",
            code="validation_error",
        )
    if parts.username is not None or parts.password is not None:
        raise ToolExecutionError("URL 不允许包含用户名或密码", code="validation_error")
    if port not in (None, 80, 443):
        raise ToolExecutionError(
            "只支持默认 HTTP/HTTPS 端口",
            code="validation_error",
        )

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc,
            parts.path or "/",
            parts.query,
            "",
        )
    )


def _is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return address.is_global or (
        isinstance(address, ipaddress.IPv6Address) and address in TEREDO_NETWORK
    )


async def resolve_public_addresses(
    hostname: str,
) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
    try:
        address_infos = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            None,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ToolExecutionError("网页域名解析失败", code="dependency_unavailable") from exc

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for address_info in address_infos:
        raw_address = address_info[4][0]
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise ToolExecutionError(
                "网页域名解析结果无效",
                code="dependency_unavailable",
            ) from exc
        if address not in addresses:
            addresses.append(address)

    if not addresses:
        raise ToolExecutionError("网页域名没有可用地址", code="dependency_unavailable")
    return tuple(addresses)


async def _assert_public_url(url: str) -> None:
    hostname = urlsplit(url).hostname
    if not hostname:
        raise ToolExecutionError("URL 缺少主机名", code="validation_error")

    try:
        literal_address = ipaddress.ip_address(hostname)
    except ValueError:
        literal_address = None

    addresses = (
        (literal_address,)
        if literal_address is not None
        else await resolve_public_addresses(hostname)
    )
    if not all(_is_public_address(address) for address in addresses):
        raise ToolExecutionError(
            "目标地址被安全策略阻止",
            code="permission_denied",
        )


def _decode_html(body: bytes, encoding: str | None) -> str:
    if encoding:
        try:
            return body.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            pass

    detected = from_bytes(body).best()
    if detected is not None:
        return str(detected)
    return body.decode("utf-8", errors="replace")


def _content_type(response: httpx.Response) -> str:
    return response.headers.get("content-type", "").split(";", 1)[0].strip().lower()


def _needs_inline_separator(left: str, right: str) -> bool:
    if not left or not right:
        return False
    left_character = left[-1]
    right_character = right[0]
    return (
        (left_character.isalnum() or left_character in ")]`")
        and (right_character.isalnum() or right_character in "([`-")
    )


def _last_text(element: lxml_html.HtmlElement) -> str:
    if not isinstance(element.tag, str):
        return ""
    return "".join(element.itertext(with_tail=False)).rstrip()


def _clean_html_for_extraction(html: str) -> tuple[str, bool]:
    parser = lxml_html.HTMLParser(encoding="utf-8", no_network=True, recover=True)
    root = lxml_html.fromstring(html, parser=parser)
    skeleton_elements = root.xpath("//*[@data-cds='Skeleton']")

    for element in skeleton_elements + root.xpath("//script | //style | //template"):
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    for parent in root.iter():
        if parent.text and len(parent):
            first_child = parent[0]
            if isinstance(first_child.tag, str) and first_child.tag in INLINE_ELEMENTS and _needs_inline_separator(
                parent.text, first_child.text or ""
            ):
                first_child.text = f" {first_child.text or ''}"
        for child in parent:
            if child.tail and _needs_inline_separator(_last_text(child), child.tail):
                child.tail = f" {child.tail}"

    return lxml_html.tostring(root, encoding="unicode"), bool(skeleton_elements)


def _add_markdown_boundary_spacing(
    markdown: str,
    pattern: re.Pattern[str],
) -> str:
    chunks: list[str] = []
    last_end = 0
    for match in pattern.finditer(markdown):
        value = match.group(0)
        before = markdown[match.start() - 1] if match.start() else ""
        after = markdown[match.end()] if match.end() < len(markdown) else ""
        if _needs_inline_separator(before, value[0]):
            value = f" {value}"
        if _needs_inline_separator(value[-1], after):
            value = f"{value} "
        chunks.extend((markdown[last_end : match.start()], value))
        last_end = match.end()
    chunks.append(markdown[last_end:])
    return "".join(chunks)


def _normalize_markdown_spacing(markdown: str) -> str:
    markdown = _add_markdown_boundary_spacing(markdown, MARKDOWN_LINK_PATTERN)
    return _add_markdown_boundary_spacing(markdown, INLINE_CODE_PATTERN)


def _normalized_content(value: str) -> str:
    value = re.sub(r"\[([^\]\n]+)\]\([^\)\n]+\)", r"\1", value)
    value = value.replace("`", "")
    return " ".join(value.split()).casefold()


def _main_list_items(html: str) -> tuple[str, ...]:
    parser = lxml_html.HTMLParser(encoding="utf-8", no_network=True, recover=True)
    root = lxml_html.fromstring(html, parser=parser)
    candidates = root.xpath(
        "//*[@id='content-container' or @role='main'] | //main | //article"
    )
    if isinstance(root.tag, str) and root.tag in {"main", "article"}:
        candidates.insert(0, root)

    for candidate in candidates:
        items = candidate.xpath(".//li[not(.//li)]")
        texts = tuple(
            " ".join(" ".join(item.itertext()).split())
            for item in items
            if " ".join(" ".join(item.itertext()).split())
        )
        meaningful_texts = tuple(text for text in texts if len(text) >= 8)
        if meaningful_texts:
            return meaningful_texts
    return ()


def _needs_recall(html: str, markdown: str) -> bool:
    list_items = _main_list_items(html)
    if not list_items:
        return False
    normalized_markdown = _normalized_content(markdown)
    return any(_normalized_content(item) not in normalized_markdown for item in list_items)


async def fetch_html(url: str) -> FetchedPage:
    current_url = normalize_url(url)

    async with httpx.AsyncClient(
        timeout=DEFAULT_HTTP_TIMEOUT,
        follow_redirects=False,
        headers={"Accept": "text/html,application/xhtml+xml"},
        trust_env=False,
    ) as client:
        request_headers = {"User-Agent": DEFAULT_USER_AGENT}
        has_used_fallback_user_agent = False
        for redirect_count in range(MAX_REDIRECTS + 1):
            await _assert_public_url(current_url)
            try:
                response = await client.get(current_url, headers=request_headers)
            except httpx.TimeoutException as exc:
                raise ToolExecutionError("网页请求超时", code="dependency_unavailable") from exc
            except httpx.RequestError as exc:
                raise ToolExecutionError("网页请求失败", code="dependency_unavailable") from exc

            try:
                if response.status_code == 403 and not has_used_fallback_user_agent:
                    request_headers = {"User-Agent": FALLBACK_USER_AGENT}
                    has_used_fallback_user_agent = True
                    continue

                if response.is_redirect or response.status_code in {300, 305, 307, 308}:
                    if redirect_count >= MAX_REDIRECTS:
                        raise ToolExecutionError(
                            "网页重定向次数超过限制",
                            code="limit_exceeded",
                        )
                    location = response.headers.get("location")
                    if not location:
                        raise ToolExecutionError("网页重定向缺少目标地址")
                    current_url = normalize_url(urljoin(current_url, location))
                    continue

                if response.status_code >= 400:
                    raise ToolExecutionError(
                        f"网页返回 HTTP {response.status_code}",
                    )
                if response.status_code < 200:
                    raise ToolExecutionError(f"网页返回 HTTP {response.status_code}")

                content_type = _content_type(response)
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise ToolExecutionError(
                        f"不支持的网页内容类型: {content_type or 'unknown'}",
                        code="validation_error",
                    )

                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > MAX_RAW_HTML_BYTES:
                            raise ToolExecutionError(
                                "网页响应超过大小限制",
                                code="limit_exceeded",
                            )
                    except ValueError:
                        pass

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RAW_HTML_BYTES:
                        raise ToolExecutionError(
                            "网页响应超过大小限制",
                            code="limit_exceeded",
                        )
                html = await asyncio.to_thread(_decode_html, bytes(body), response.encoding)
                if not html.strip():
                    raise ToolExecutionError("网页没有可读取的 HTML 内容")
                return FetchedPage(
                    final_url=current_url,
                    status_code=response.status_code,
                    content_type=content_type,
                    html=html,
                    icon_url=urljoin(current_url, "/favicon.ico"),
                )
            finally:
                await response.aclose()

    raise ToolExecutionError("网页重定向处理失败")


def extract_html(html: str, url: str) -> ExtractedPage:
    html, has_skeleton = _clean_html_for_extraction(html)
    document = extract_with_metadata(
        html,
        url=url,
        favor_recall=False,
        include_comments=False,
        output_format="markdown",
        include_tables=True,
        include_images=False,
        include_formatting=True,
        include_links=True,
    )
    used_recall = False

    precision_markdown = (document.text or "") if document is not None else ""
    if document is None or (has_skeleton and _needs_recall(html, precision_markdown)):
        recall_document = extract_with_metadata(
            html,
            url=url,
            favor_recall=True,
            include_comments=False,
            output_format="markdown",
            include_tables=True,
            include_images=False,
            include_formatting=True,
            include_links=True,
        )
        recall_markdown = (recall_document.text or "") if recall_document is not None else ""
        if recall_markdown:
            document = recall_document
            used_recall = True

    if document is None:
        raise ToolExecutionError("网页没有可提取的正文")
    markdown = (document.text or "").strip()
    if not markdown:
        raise ToolExecutionError("网页没有可提取的正文")
    if used_recall:
        markdown = _normalize_markdown_spacing(markdown)

    def optional_string(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    return ExtractedPage(
        markdown=markdown,
        title=optional_string(document.title) or "",
        author=optional_string(document.author),
        date=optional_string(document.date),
        site_name=optional_string(document.sitename),
        language=optional_string(document.language),
    )


async def fetch_and_extract(url: str) -> tuple[FetchedPage, ExtractedPage]:
    page = await fetch_html(url)
    extracted = await asyncio.to_thread(extract_html, page.html, page.final_url)
    return page, extracted
