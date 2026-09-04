# -*- coding: utf-8 -*-
"""离线 tiktoken 编码器。"""

from hashlib import sha1
import os
from pathlib import Path
from tempfile import gettempdir

import tiktoken
from loguru import logger


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


def _write_atomic(path: Path, data: bytes) -> None:
    # 临时文件 + os.replace，保证读者只会看到完整副本；Windows 上若目标
    # 恰被其他进程打开会抛 PermissionError，此时保留旧文件并告警即可。
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(data)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.warning(f"写入 tiktoken 词表缓存失败 {path}: {exc}")
        tmp_path.unlink(missing_ok=True)


def seed_bundled_encodings() -> None:
    """确保 tiktoken 缓存中存在内置词表。

    token 计数是高频操作（逐消息、逐轮迭代、列表接口逐条目），缓存文件
    已存在时必须跳过写入，否则每次计数都会产生数 MB 的同步磁盘 I/O，
    阻塞事件循环。内容有效性不需要在这里校验：tiktoken 加载时会自行
    做哈希校验，损坏或不匹配的缓存会被它删除重取；本地兜底见
    get_encoding 的重建重试。
    """
    for encoding_name in _ENCODING_URLS:
        resource_path = _ENCODING_RESOURCE_DIR / f"{encoding_name}.tiktoken"
        cache_path = _cache_path(encoding_name)
        if cache_path.exists():
            continue
        _write_atomic(cache_path, resource_path.read_bytes())


def get_encoding(encoding_name: str = "o200k_base") -> tiktoken.Encoding:
    """将内置词表预置到 tiktoken 缓存后加载编码器。"""
    if encoding_name not in _ENCODING_URLS:
        raise ValueError(f"不支持的 tiktoken 编码: {encoding_name}")
    seed_bundled_encodings()
    try:
        return tiktoken.get_encoding(encoding_name)
    except Exception:
        # 大小一致但内容损坏的缓存（位翻转、第三方写入）不会被跳过逻辑
        # 识别，这里删除重写后重试一次，仍失败则让异常抛出。
        logger.warning(f"tiktoken 编码 {encoding_name} 加载失败，重建缓存后重试")
        resource_path = _ENCODING_RESOURCE_DIR / f"{encoding_name}.tiktoken"
        _write_atomic(_cache_path(encoding_name), resource_path.read_bytes())
        return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = "o200k_base") -> int:
    """统计文本的 token 数量。"""
    if not text:
        return 0
    return len(get_encoding(encoding_name).encode(text))
