"""
ID 生成辅助函数。
"""

from nanoid import generate


def generate_id(size: int = 21) -> str:
    """
    生成唯一 ID。

    Args:
        size: ID 长度，默认 21。

    Returns:
        唯一 ID 字符串。
    """
    return generate(size=size)
