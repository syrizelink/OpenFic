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
# 已完成内容校验的编码。校验需要完整读取缓存与内置词表（数 MB），每个
# 编码每进程只做一次；GIL 下 set 的读取与添加均为原子操作，并发首调
# 最坏重复校验一次，结果幂等，无需加锁。
_VALIDATED_ENCODINGS: set[str] = set()


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
    """确保 tiktoken 缓存中存在内置词表，供 LangChain 直接加载。

    token 计数是高频操作（逐消息、逐轮迭代、列表接口逐条目），这里只
    补缺失的缓存文件（一次 exists 检查）；已存在时必须跳过写入，否则
    每次计数都会产生数 MB 的同步磁盘 I/O，阻塞事件循环。缓存内容是否
    与内置词表一致由 _ensure_valid_cache 在加载前校验。
    """
    for encoding_name in _ENCODING_URLS:
        resource_path = _ENCODING_RESOURCE_DIR / f"{encoding_name}.tiktoken"
        cache_path = _cache_path(encoding_name)
        if cache_path.exists():
            continue
        _write_atomic(cache_path, resource_path.read_bytes())


def _ensure_valid_cache(encoding_name: str) -> None:
    """加载前校验缓存内容与内置词表一致，缺失或损坏时原子重写。

    tiktoken 只有在缓存存在且哈希正确时才会离线命中缓存，损坏的缓存
    会被它删除并联网重取。因此校验必须先于 tiktoken.get_encoding()，
    否则在线机器上损坏缓存会触发不必要的联网下载，离线机器则加载
    失败。为避免高频计数反复读文件，每个编码每进程只校验一次，后续
    调用直接放行。
    """
    if encoding_name in _VALIDATED_ENCODINGS:
        return
    _VALIDATED_ENCODINGS.add(encoding_name)
    bundled = (_ENCODING_RESOURCE_DIR / f"{encoding_name}.tiktoken").read_bytes()
    cache_path = _cache_path(encoding_name)
    try:
        if cache_path.read_bytes() == bundled:
            return
    except OSError:
        pass
    logger.warning(f"tiktoken 词表缓存缺失或损坏，从内置词表重建: {cache_path}")
    _write_atomic(cache_path, bundled)


def get_encoding(encoding_name: str = "o200k_base") -> tiktoken.Encoding:
    """校验并修复缓存后加载编码器，保证不依赖网络。"""
    if encoding_name not in _ENCODING_URLS:
        raise ValueError(f"不支持的 tiktoken 编码: {encoding_name}")
    seed_bundled_encodings()
    _ensure_valid_cache(encoding_name)
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = "o200k_base") -> int:
    """统计文本的 token 数量。"""
    if not text:
        return 0
    return len(get_encoding(encoding_name).encode(text))
