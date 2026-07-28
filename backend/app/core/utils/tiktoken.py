# -*- coding: utf-8 -*-
"""离线 tiktoken 编码器。"""

from hashlib import sha1
import os
from pathlib import Path
from tempfile import gettempdir

import tiktoken


_ENCODING_RESOURCE_DIR = Path(__file__).parents[1] / "resources" / "tiktoken"
_ENCODING_URLS = {
    "cl100k_base": "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken",
    "o200k_base": "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken",
}


def _cache_dir() -> Path:
    configured_dir = os.getenv("TIKTOKEN_CACHE_DIR") or os.getenv("DATA_GYM_CACHE_DIR")
    return (
        Path(configured_dir)
        if configured_dir
        else Path(gettempdir()) / "data-gym-cache"
    )


def _cache_path(encoding_name: str) -> Path:
    source_url = _ENCODING_URLS.get(encoding_name)
    if source_url is None:
        raise ValueError(f"不支持的 tiktoken 编码: {encoding_name}")
    return _cache_dir() / sha1(source_url.encode()).hexdigest()


def seed_bundled_encodings() -> None:
    """将内置词表写入 tiktoken 默认缓存，供 LangChain 直接加载。"""
    for encoding_name in _ENCODING_URLS:
        resource_path = _ENCODING_RESOURCE_DIR / f"{encoding_name}.tiktoken"
        cache_path = _cache_path(encoding_name)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(resource_path.read_bytes())


def get_encoding(encoding_name: str = "o200k_base") -> tiktoken.Encoding:
    """将内置词表预置到 tiktoken 缓存后加载编码器。"""
    if encoding_name not in _ENCODING_URLS:
        raise ValueError(f"不支持的 tiktoken 编码: {encoding_name}")
    seed_bundled_encodings()
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = "o200k_base") -> int:
    """统计文本的 token 数量。"""
    if not text:
        return 0
    return len(get_encoding(encoding_name).encode(text))
