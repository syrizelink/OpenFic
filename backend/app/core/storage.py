# -*- coding: utf-8 -*-
"""
文件存储工具模块。

提供封面图片的保存、调整尺寸等功能。
"""

import io
import time
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from app.settings import settings


def ensure_covers_dir() -> Path:
    """
    确保封面存储目录存在。

    Returns:
        封面存储目录路径。
    """
    covers_dir = settings.covers_dir
    covers_dir.mkdir(parents=True, exist_ok=True)
    return covers_dir


async def save_cover_file(project_id: str, cover_file: UploadFile) -> str:
    """
    保存上传的封面文件。

    将上传的图片调整为宽度 600px（保持 2:3 比例），并保存为 JPG 格式。

    Args:
        project_id: 项目 ID。
        cover_file: 上传的封面文件。

    Returns:
        保存的文件相对路径（相对于 covers_dir）。
    """
    ensure_covers_dir()

    # 读取上传的图片
    content = await cover_file.read()
    image = Image.open(io.BytesIO(content))

    # 转换为 RGB（如果是  RGBA 或其他格式）
    if image.mode != "RGB":
        image = image.convert("RGB")  # type: ignore[assignment]

    # 调整尺寸：宽度 600px，高度按比例计算（如果已经裁剪为 2:3，则高度为 900px）
    target_width = 600
    target_height = int(target_width * 1.5)  # 2:3 比例

    # 使用 LANCZOS 插值调整尺寸
    image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)  # type: ignore[assignment]

    # 保存为 JPG
    filename = f"{project_id}.jpg"
    filepath = settings.covers_dir / filename

    image.save(filepath, "JPEG", quality=85, optimize=True)

    return filename


def delete_cover_file(project_id: str) -> None:
    """
    删除封面文件。

    Args:
        project_id: 项目 ID。
    """
    filename = f"{project_id}.jpg"
    filepath = settings.covers_dir / filename

    if filepath.exists():
        filepath.unlink()


def get_cover_url(cover_path: str | None) -> str | None:
    """
    获取封面访问 URL。

    Args:
        cover_path: 封面文件路径（文件名）。

    Returns:
        封面访问 URL，如果没有封面则返回 None。
    """
    if not cover_path:
        return None

    # 添加时间戳避免浏览器缓存
    timestamp = int(time.time())
    return f"/covers/{cover_path}?t={timestamp}"
