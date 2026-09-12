# -*- coding: utf-8 -*-
"""
Modul utilitas penyimpanan berkas.

Menyediakan fungsi penyimpanan gambar sampul, penyesuaian ukuran, dan lainnya.
"""

import io
import time
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from app.settings import settings


def ensure_covers_dir() -> Path:
    """
    Memastikan direktori penyimpanan sampul ada.

    Returns:
        Path direktori penyimpanan sampul.
    """
    covers_dir = settings.covers_dir
    covers_dir.mkdir(parents=True, exist_ok=True)
    return covers_dir


def ensure_character_images_dir() -> Path:
    """Memastikan direktori penyimpanan avatar tokoh ada."""
    character_images_dir = settings.character_images_dir
    character_images_dir.mkdir(parents=True, exist_ok=True)
    return character_images_dir


async def save_cover_file(project_id: str, cover_file: UploadFile) -> str:
    """
    Menyimpan berkas sampul yang diunggah.

    Menyesuaikan gambar yang diunggah menjadi lebar 600px (mempertahankan rasio 2:3),
    lalu menyimpannya dalam format JPG.

    Args:
        project_id: ID proyek.
        cover_file: berkas sampul yang diunggah.

    Returns:
        Path relatif berkas yang disimpan (relatif terhadap covers_dir).
    """
    ensure_covers_dir()

    # Baca gambar yang diunggah
    content = await cover_file.read()
    image = Image.open(io.BytesIO(content))

    # Konversi ke RGB (jika RGBA atau format lain)
    if image.mode != "RGB":
        image = image.convert("RGB")  # type: ignore[assignment]

    # Sesuaikan ukuran: lebar 600px, tinggi dihitung proporsional
    # (jika sudah dipotong ke 2:3, tingginya menjadi 900px)
    target_width = 600
    target_height = int(target_width * 1.5)  # rasio 2:3

    # Sesuaikan ukuran memakai interpolasi LANCZOS
    image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)  # type: ignore[assignment]

    # Simpan sebagai JPG
    filename = f"{project_id}.jpg"
    filepath = settings.covers_dir / filename

    image.save(filepath, "JPEG", quality=85, optimize=True)

    return filename


def delete_cover_file(project_id: str) -> None:
    """
    Menghapus berkas sampul.

    Args:
        project_id: ID proyek.
    """
    filename = f"{project_id}.jpg"
    filepath = settings.covers_dir / filename

    if filepath.exists():
        filepath.unlink()


def get_cover_url(cover_path: str | None) -> str | None:
    """
    Mengambil URL akses sampul.

    Args:
        cover_path: path berkas sampul (nama berkas).

    Returns:
        URL akses sampul, atau None jika tidak ada sampul.
    """
    if not cover_path:
        return None

    # Tambahkan timestamp untuk menghindari cache peramban
    timestamp = int(time.time())
    return f"/covers/{cover_path}?t={timestamp}"


async def save_character_image(character_id: str, image_file: UploadFile) -> str:
    """Menyimpan berkas avatar tokoh."""
    ensure_character_images_dir()
    content = await image_file.read()
    image = Image.open(io.BytesIO(content))

    if image.mode != "RGB":
        image = image.convert("RGB")  # type: ignore[assignment]

    image = image.resize((256, 256), Image.Resampling.LANCZOS)  # type: ignore[assignment]
    filename = f"{character_id}-{time.time_ns()}.jpg"
    filepath = settings.character_images_dir / filename
    image.save(filepath, "JPEG", quality=88, optimize=True)
    return filename


def delete_character_image(image_path: str) -> None:
    """Menghapus berkas avatar tokoh."""
    filepath = settings.character_images_dir / image_path
    if filepath.exists():
        filepath.unlink()


def get_character_image_url(image_path: str | None) -> str | None:
    """Mengambil URL akses avatar tokoh."""
    if not image_path:
        return None
    return f"/character-images/{image_path}"
