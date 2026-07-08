# -*- coding: utf-8 -*-
"""
Tiktoken 辅助工具。
"""

import tiktoken
from loguru import logger

def get_encoding(encoding_name: str = "o200k_base") -> tiktoken.Encoding:
    """
    获取 tiktoken 编码器。

    优先使用指定的编码名称，如果失败则回退到 cl100k_base。

    Args:
        encoding_name: 编码名称，默认为 o200k_base。

    Returns:
        tiktoken.Encoding 实例。
    """
    try:
        return tiktoken.get_encoding(encoding_name)
    except Exception as e:
        fallback = "cl100k_base"
        if encoding_name != fallback:
            logger.warning(f"无法加载编码 {encoding_name}，回退到 {fallback}: {e}")
            try:
                return tiktoken.get_encoding(fallback)
            except Exception as e2:
                logger.error(f"无法加载回退编码 {fallback}: {e2}")
                raise e2
        else:
            logger.error(f"无法加载编码 {encoding_name}: {e}")
            raise e


def count_tokens(text: str, encoding_name: str = "o200k_base") -> int:
    """统计文本的 token 数量。"""
    if not text:
        return 0
    return len(get_encoding(encoding_name).encode(text))
