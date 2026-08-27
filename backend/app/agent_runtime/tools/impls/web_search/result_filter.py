"""联网搜索结果的 provider 无关后处理。"""

from collections.abc import Iterable
from urllib.parse import urlparse

from app.agent_runtime.tools.impls.web_search.providers.base import WebSearchResult


def normalize_domain_filters(domains: Iterable[str]) -> list[str]:
    normalized_domains: list[str] = []
    seen_domains: set[str] = set()
    for domain in domains:
        candidate = domain.strip().lower()
        if not candidate:
            continue
        try:
            hostname = urlparse(
                candidate if "://" in candidate else f"//{candidate}"
            ).hostname
        except ValueError:
            hostname = None
        normalized_domain = hostname.rstrip(".") if hostname else ""
        if normalized_domain and normalized_domain not in seen_domains:
            seen_domains.add(normalized_domain)
            normalized_domains.append(normalized_domain)
    return normalized_domains


def filter_web_search_results(
    results: list[WebSearchResult], domains: Iterable[str]
) -> list[WebSearchResult]:
    blocked_domains = set(normalize_domain_filters(domains))
    if not blocked_domains:
        return results

    filtered_results: list[WebSearchResult] = []
    for result in results:
        try:
            hostname = urlparse(result.url).hostname
        except ValueError:
            hostname = None
        normalized_hostname = hostname.rstrip(".").lower() if hostname else ""
        if normalized_hostname and any(
            normalized_hostname == domain
            or normalized_hostname.endswith(f".{domain}")
            for domain in blocked_domains
        ):
            continue
        filtered_results.append(result)
    return filtered_results
