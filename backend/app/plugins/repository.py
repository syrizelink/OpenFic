"""Download a public GitHub repository's branch archive."""

from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING, Literal
from urllib.parse import quote, unquote

import httpx
from pydantic import ValidationError

from app.plugins.manifest import Manifest
from app.plugins.package_builder import MAX_PACKAGE_BYTES

if TYPE_CHECKING:
    from app.plugins.host import InstallProgress

GITHUB_REPOSITORY = re.compile(
    r"https://github\.com/([a-z0-9][a-z0-9-]{0,38})/([a-z0-9_.-]{1,104})(?:/tree/([^?#\s]+?))?/?",
    re.IGNORECASE | re.ASCII,
)
MAX_PREFLIGHT_BYTES = 1024 * 1024


class RepositoryDownloadError(Exception):
    def __init__(
        self,
        kind: Literal["invalid", "not_found", "too_large", "timeout", "upstream"],
        message: str,
    ):
        super().__init__(message)
        self.kind = kind


async def _read_preflight_response(
    client: httpx.AsyncClient,
    url: str,
    *,
    is_manifest: bool = False,
    branch: bool = False,
) -> bytes:
    async with client.stream("GET", url) as response:
        if response.status_code == 404:
            if is_manifest:
                raise RepositoryDownloadError(
                    "invalid", "Repository must contain a root plugin.json"
                )
            if branch:
                raise RepositoryDownloadError(
                    "not_found", "GitHub branch not found or repository is not public"
                )
            raise RepositoryDownloadError(
                "not_found", "GitHub repository not found or not public"
            )
        response.raise_for_status()
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise RepositoryDownloadError(
                "upstream", "Unexpected GitHub response encoding"
            )
        buffer = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
            if len(buffer) + len(chunk) > MAX_PREFLIGHT_BYTES:
                message = (
                    "Plugin manifest exceeds 1 MiB"
                    if is_manifest
                    else "GitHub commit metadata exceeds 1 MiB"
                )
                raise RepositoryDownloadError(
                    "too_large" if is_manifest else "upstream", message
                )
            buffer.extend(chunk)
        return bytes(buffer)


async def download_repository(url: str, progress: InstallProgress | None) -> bytes:
    match = GITHUB_REPOSITORY.fullmatch(url.strip())
    if not match:
        raise RepositoryDownloadError(
            "invalid", "Enter a public GitHub repository or branch URL"
        )
    owner, repo, branch_path = match.groups()
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if repo in {"", ".", ".."} or len(repo) > 100:
        raise RepositoryDownloadError("invalid", "Invalid GitHub repository name")
    branch = None
    if branch_path is not None:
        try:
            branch = unquote(branch_path, errors="strict")
        except UnicodeDecodeError as error:
            raise RepositoryDownloadError(
                "invalid", "Invalid GitHub branch name"
            ) from error
        if (
            re.search(r"[\x00-\x20\x7f~^:?*\[\\]|\.\.|@\{", branch)
            or branch == "@"
            or branch.endswith(".")
            or any(
                not part or part.startswith(".") or part.endswith(".lock")
                for part in branch.split("/")
            )
        ):
            raise RepositoryDownloadError("invalid", "Invalid GitHub branch name")
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    ref_url = (
        f"{api_url}/git/ref/heads/{quote(branch, safe='/')}"
        if branch
        else f"{api_url}/commits/HEAD"
    )
    if progress:
        await progress("downloading", 0)
    buffer = bytearray()
    try:
        async with asyncio.timeout(90):
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=False,
                headers={"Accept-Encoding": "identity"},
            ) as client:
                metadata = await _read_preflight_response(
                    client, ref_url, branch=branch is not None
                )
                try:
                    commit = json.loads(metadata)
                except ValueError as error:
                    raise RepositoryDownloadError(
                        "upstream", "Invalid GitHub commit metadata"
                    ) from error
                if branch and isinstance(commit, dict):
                    commit = commit.get("object")
                sha = commit.get("sha") if isinstance(commit, dict) else None
                if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
                    raise RepositoryDownloadError(
                        "upstream", "Invalid GitHub commit SHA"
                    )

                manifest = await _read_preflight_response(
                    client,
                    f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/plugin.json",
                    is_manifest=True,
                )
                try:
                    Manifest.model_validate_json(manifest)
                except ValidationError as error:
                    raise RepositoryDownloadError(
                        "invalid",
                        "Invalid manifest: root plugin.json does not match the plugin format",
                    ) from error

                archive_url = f"https://codeload.github.com/{owner}/{repo}/zip/{sha}"
                async with client.stream("GET", archive_url) as response:
                    if response.status_code == 404:
                        raise RepositoryDownloadError(
                            "not_found", "GitHub repository not found or not public"
                        )
                    response.raise_for_status()
                    if (
                        response.headers.get("content-encoding", "identity").lower()
                        != "identity"
                    ):
                        raise RepositoryDownloadError(
                            "upstream", "Unexpected GitHub archive encoding"
                        )
                    length = response.headers.get("content-length", "")
                    total = (
                        int(length)
                        if length.isascii() and length.isdecimal() and len(length) <= 20
                        else 0
                    )
                    if total > MAX_PACKAGE_BYTES:
                        raise RepositoryDownloadError(
                            "too_large", "Package exceeds 20 MiB"
                        )
                    last = 0
                    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                        if len(buffer) + len(chunk) > MAX_PACKAGE_BYTES:
                            raise RepositoryDownloadError(
                                "too_large", "Package exceeds 20 MiB"
                            )
                        buffer.extend(chunk)
                        if progress and len(buffer) < total:
                            value = len(buffer) * 45 // total
                            if value >= last + 4:
                                last = value
                                await progress("downloading", value)
    except (TimeoutError, httpx.TimeoutException) as error:
        raise RepositoryDownloadError(
            "timeout", "GitHub repository download timed out"
        ) from error
    except httpx.HTTPError as error:
        raise RepositoryDownloadError(
            "upstream", "Could not download GitHub repository"
        ) from error
    if progress:
        await progress("downloading", 45)
    return bytes(buffer)
