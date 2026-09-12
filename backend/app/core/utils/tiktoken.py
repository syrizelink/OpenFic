# -*- coding: utf-8 -*-
"""Encoder tiktoken offline."""

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
# Encoding yang kontennya sudah divalidasi. Validasi perlu membaca cache dan tabel
# kata bawaan secara penuh (beberapa MB), jadi tiap encoding hanya sekali per proses;
# di bawah GIL pembacaan dan penambahan set bersifat atomik, sehingga pemanggilan
# pertama yang konkuren paling buruk hanya memvalidasi ulang sekali, hasilnya idempoten
# dan tidak perlu lock.
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
        raise ValueError(f"Encoding tiktoken tidak didukung: {encoding_name}")
    return _cache_dir() / sha1(source_url.encode()).hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    # Berkas sementara + os.replace menjamin pembaca hanya melihat salinan utuh;
    # di Windows jika target sedang dibuka proses lain akan melempar PermissionError,
    # dalam kasus itu cukup pertahankan berkas lama dan beri peringatan.
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(data)
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.warning(f"Gagal menulis cache tabel kata tiktoken {path}: {exc}")
        tmp_path.unlink(missing_ok=True)


def seed_bundled_encodings() -> None:
    """Memastikan tabel kata bawaan ada di cache tiktoken agar LangChain dapat
    memuatnya langsung.

    Penghitungan token adalah operasi berfrekuensi tinggi (per pesan, per iterasi
    putaran, per entri pada antarmuka daftar), jadi di sini hanya berkas cache yang
    hilang yang dilengkapi (satu kali pemeriksaan exists); jika sudah ada, penulisan
    wajib dilewati, kalau tidak setiap penghitungan akan menimbulkan I/O disk sinkron
    beberapa MB dan memblokir event loop. Kesesuaian isi cache dengan tabel kata bawaan
    divalidasi oleh _ensure_valid_cache sebelum pemuatan.
    """
    for encoding_name in _ENCODING_URLS:
        resource_path = _ENCODING_RESOURCE_DIR / f"{encoding_name}.tiktoken"
        cache_path = _cache_path(encoding_name)
        if cache_path.exists():
            continue
        _write_atomic(cache_path, resource_path.read_bytes())


def _ensure_valid_cache(encoding_name: str) -> None:
    """Memvalidasi kesesuaian isi cache dengan tabel kata bawaan sebelum pemuatan,
    dan menulis ulang secara atomik jika hilang atau rusak.

    tiktoken hanya memakai cache secara offline bila cache ada dan hash-nya benar;
    cache yang rusak akan dihapus dan diambil ulang lewat jaringan. Karena itu validasi
    harus dilakukan sebelum tiktoken.get_encoding(), kalau tidak cache rusak pada mesin
    daring akan memicu unduhan jaringan yang tidak perlu, sedangkan mesin luring gagal
    memuat. Untuk menghindari pembacaan berkas berulang pada penghitungan berfrekuensi
    tinggi, tiap encoding hanya divalidasi sekali per proses, pemanggilan berikutnya
    langsung diteruskan.
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
    logger.warning(
        f"Cache tabel kata tiktoken hilang atau rusak, dibangun ulang dari tabel "
        f"kata bawaan: {cache_path}"
    )
    _write_atomic(cache_path, bundled)


def get_encoding(encoding_name: str = "o200k_base") -> tiktoken.Encoding:
    """Memuat encoder setelah cache divalidasi dan diperbaiki, menjamin tanpa jaringan."""
    if encoding_name not in _ENCODING_URLS:
        raise ValueError(f"Encoding tiktoken tidak didukung: {encoding_name}")
    seed_bundled_encodings()
    _ensure_valid_cache(encoding_name)
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = "o200k_base") -> int:
    """Menghitung jumlah token dalam teks."""
    if not text:
        return 0
    return len(get_encoding(encoding_name).encode(text))
