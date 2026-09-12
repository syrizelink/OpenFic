# -*- coding: utf-8 -*-
"""
FastEmbed Embeddings - membungkus model lokal fastembed menjadi antarmuka
LangChain Embeddings.

Inferensi fastembed bersifat sinkron; di sini pemanggilan sinkron dipindahkan keluar
dari event loop melalui asyncio.to_thread agar tidak memblokir pemrosesan permintaan.

Strategi unduh model: fastembed secara default mencoba HuggingFace lebih dulu, tetapi
HF tidak dapat dijangkau di sebagian lingkungan jaringan sehingga menyebabkan hang tak
terbatas. Di sini diutamakan unduh langsung dari GCS (Google Cloud Storage) dan dimuat
dengan HF_HUB_OFFLINE=1 untuk melewati permintaan jaringan HF. Hanya jika model tidak
memiliki sumber GCS baru kembali ke HF.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tarfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings
from loguru import logger

from app.settings import BACKEND_DATA_DIR

_FASTEMBED_CACHE_DIR = BACKEND_DATA_DIR / "fastembed_cache"
_DOWNLOAD_TIMEOUT_SECONDS = 120


def _resolve_cache_dir() -> Path:
    cache_dir = _FASTEMBED_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _build_opener() -> urllib.request.OpenerDirector:
    """Membangun URL opener yang mendukung proxy sistem.

    urllib.request.urlopen secara default tidak membaca variabel lingkungan
    HTTP_PROXY/HTTPS_PROXY, sehingga proxy perlu disuntikkan eksplisit melalui
    ProxyHandler agar model tetap dapat diunduh di lingkungan jaringan berproxy.
    """
    proxies = urllib.request.getproxies()
    if proxies:
        return urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
    return urllib.request.build_opener()


def _download_with_timeout(url: str, dest: Path, *, timeout_seconds: int) -> None:
    """Mengunduh file dari URL ke dest, dengan batas waktu koneksi dan baca.

    Otomatis memakai proxy sistem (variabel lingkungan HTTP_PROXY/HTTPS_PROXY).
    Jika jaringan tidak dapat dijangkau, gagal dalam batas waktu dan melempar
    kesalahan yang jelas alih-alih hang tak terbatas.
    Mencatat log progres setiap 10 MiB.
    """
    import socket

    opener = _build_opener()
    try:
        with opener.open(url, timeout=timeout_seconds) as response:  # noqa: S310
            total = int(response.headers.get("Content-Length", 0))
            written = 0
            last_report = 0
            chunk = 64 * 1024
            report_interval = 10 * 1024 * 1024  # 10 MiB
            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    written += len(chunk)
                    if total > 0 and written - last_report >= report_interval:
                        logger.info(
                            "Progres unduh model: {:.0%} ({:.1f} / {:.1f} MiB)",
                            written / total,
                            written / 1048576,
                            total / 1048576,
                        )
                        last_report = written
            if total > 0 and written != total:
                raise IOError(
                    f"Unduh model tidak lengkap: tertulis {written} bita, "
                    f"diharapkan {total} bita"
                )
    except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            f"Unduh model bawaan gagal (jaringan tidak terjangkau atau timeout): {url}\n"
            f"Kesalahan: {exc}\n"
            "Periksa koneksi jaringan atau pengaturan proxy lalu coba lagi, atau unduh "
            f"model manual ke direktori {_FASTEMBED_CACHE_DIR}."
        ) from exc


def _list_supported_models(model_class: Any, model_name: str) -> dict[str, Any] | None:
    list_supported_models = getattr(model_class, "list_supported_models", None)
    if not callable(list_supported_models):
        return None
    for spec in list_supported_models():
        if spec["model"] == model_name:
            return spec
    return None


def _ensure_model_from_gcs(
    model_class: Any,
    model_name: str,
    cache_dir: Path,
) -> bool:
    """Jika model punya sumber GCS dan belum di-cache, unduh dari GCS lalu ekstrak.

    Mengembalikan True berarti model sudah siap dan dapat dimuat dengan mode
    HF_HUB_OFFLINE (yaitu tanpa perlu mengakses HF).
    """
    spec = _list_supported_models(model_class, model_name)
    if spec is None:
        return False

    sources = spec.get("sources", {})
    gcs_url = sources.get("url")
    if not gcs_url:
        return False

    deprecated_tar = sources.get("_deprecated_tar_struct", False)
    fast_name = f"{'fast-' if deprecated_tar else ''}{model_name.split('/')[-1]}"
    model_dir = cache_dir / fast_name

    if model_dir.exists() and any(model_dir.iterdir()):
        return True

    tar_gz_path = cache_dir / f"{fast_name}.tar.gz"
    tmp_dir = cache_dir / "tmp" / fast_name

    logger.info("Mengunduh model fastembed dari GCS: {} -> {}", model_name, gcs_url)
    _download_with_timeout(gcs_url, tar_gz_path, timeout_seconds=120)

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(tar_gz_path), "r:gz") as tar:
        tar.extractall(str(tmp_dir))  # noqa: S202

    tar_gz_path.unlink(missing_ok=True)
    extracted = tmp_dir / fast_name
    if extracted.exists():
        extracted.rename(model_dir)
    else:
        for child in tmp_dir.iterdir():
            child.rename(model_dir)
            break
    shutil.rmtree(tmp_dir.parent, ignore_errors=True)

    logger.info("Model fastembed sudah di-cache: {} -> {}", model_name, model_dir)
    return True


def _set_hf_offline(enabled: bool) -> str | None:
    """Mengalihkan mode offline HuggingFace secara sementara
    (env var + konstanta huggingface_hub).

    huggingface_hub men-cache HF_HUB_OFFLINE saat impor, jadi menyetel env var saja
    tidak cukup; konstanta perlu diubah sekaligus. Mengembalikan nilai asli untuk
    dipulihkan.
    """
    import huggingface_hub.constants as hf_constants

    old_env = os.environ.get("HF_HUB_OFFLINE")
    old_const = hf_constants.HF_HUB_OFFLINE

    os.environ["HF_HUB_OFFLINE"] = "1" if enabled else "0"
    hf_constants.HF_HUB_OFFLINE = enabled

    return f"{old_env}|{old_const}"


def _restore_hf_offline(state: str | None) -> None:
    if state is None:
        return
    old_env, old_const = state.split("|")
    import huggingface_hub.constants as hf_constants

    if old_env == "None":
        os.environ.pop("HF_HUB_OFFLINE", None)
    else:
        os.environ["HF_HUB_OFFLINE"] = old_env
    hf_constants.HF_HUB_OFFLINE = old_const == "True"


_HF_URL = "https://huggingface.co"
_PREFLIGHT_TIMEOUT = 5.0


def _check_hf_reachable() -> None:
    """Pra-cek HTTPS apakah HuggingFace terjangkau, gagal cepat jika tidak."""
    try:
        with urllib.request.urlopen(
            urllib.request.Request(f"{_HF_URL}/api/status", method="HEAD"),
            timeout=_PREFLIGHT_TIMEOUT,
        ):
            pass
    except urllib.error.HTTPError as exc:
        if exc.code is None:
            raise
    except Exception as exc:
        raise RuntimeError(
            f"Tidak dapat terhubung ke HuggingFace ({_HF_URL} tidak terjangkau), "
            "periksa koneksi jaringan lalu coba lagi, atau unduh model manual ke "
            f"direktori {_FASTEMBED_CACHE_DIR}."
        ) from exc


def _ensure_model_from_hf(
    model_class: Any,
    model_name: str,
    cache_dir: Path,
) -> bool:
    """Untuk model tanpa sumber GCS, unduh dari HuggingFace (dengan proteksi timeout).

    Mengembalikan True berarti file model sudah siap. Jika pra-cek tidak terjangkau,
    gagal cepat dalam 5 detik.
    """
    import socket

    spec = _list_supported_models(model_class, model_name)
    if spec is None:
        return False

    sources = spec.get("sources", {})
    hf_repo = sources.get("hf")
    if not hf_repo:
        return False

    model_file = spec.get("model_file", "")
    additional_files = spec.get("additional_files", []) or []
    allow_patterns = [
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "preprocessor_config.json",
        model_file,
    ]
    allow_patterns.extend(additional_files)

    snapshot_dir = cache_dir / f"models--{hf_repo.replace('/', '--')}"
    if snapshot_dir.exists() and any(snapshot_dir.rglob("*.onnx")):
        return True

    _check_hf_reachable()
    from huggingface_hub import snapshot_download

    logger.info("Mengunduh model fastembed dari HuggingFace: {}", hf_repo)
    old_etag = os.environ.get("HF_HUB_ETAG_TIMEOUT")
    old_dl = os.environ.get("HF_HUB_DOWNLOAD_TIMEOUT")
    old_pbar = os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS")
    os.environ["HF_HUB_ETAG_TIMEOUT"] = "30"
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "120"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    try:
        snapshot_download(
            repo_id=hf_repo,
            allow_patterns=allow_patterns,
            cache_dir=str(cache_dir),
        )
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"Unduh model bawaan gagal (HuggingFace tidak terjangkau atau timeout): "
            f"{hf_repo}\n"
            f"Kesalahan: {exc}\n"
            "Periksa koneksi jaringan lalu coba lagi."
        ) from exc
    finally:
        if old_etag is None:
            os.environ.pop("HF_HUB_ETAG_TIMEOUT", None)
        else:
            os.environ["HF_HUB_ETAG_TIMEOUT"] = old_etag
        if old_dl is None:
            os.environ.pop("HF_HUB_DOWNLOAD_TIMEOUT", None)
        else:
            os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = old_dl
        if old_pbar is None:
            os.environ.pop("HF_HUB_DISABLE_PROGRESS_BARS", None)
        else:
            os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = old_pbar

    logger.info("Model fastembed sudah di-cache (HF): {} -> {}", model_name, snapshot_dir)
    return True


def _instantiate_fastembed_model(
    model_class: Any,
    model_name: str,
    cache_dir: Path,
) -> Any:
    try:
        return model_class(model_name=model_name, cache_dir=str(cache_dir))
    except TypeError as exc:
        if "cache_dir" not in str(exc):
            raise
        return model_class(model_name=model_name)


def _load_fastembed_model(model_class: Any, model_name: str) -> Any:
    """Memuat model fastembed, mengutamakan unduh dari GCS untuk melewati
    HuggingFace yang tidak terjangkau.

    Model tanpa sumber GCS (misalnya rerank) kembali ke HuggingFace dengan proteksi
    timeout, gagal cepat saat jaringan tidak terjangkau alih-alih hang tak terbatas.
    """
    cache_dir = _resolve_cache_dir()

    gcs_ready = _ensure_model_from_gcs(model_class, model_name, cache_dir)
    if gcs_ready:
        old_state = _set_hf_offline(True)
        try:
            return _instantiate_fastembed_model(model_class, model_name, cache_dir)
        finally:
            _restore_hf_offline(old_state)

    hf_ready = _ensure_model_from_hf(model_class, model_name, cache_dir)
    if hf_ready:
        old_state = _set_hf_offline(True)
        try:
            return _instantiate_fastembed_model(model_class, model_name, cache_dir)
        finally:
            _restore_hf_offline(old_state)

    return _instantiate_fastembed_model(model_class, model_name, cache_dir)


class FastEmbedEmbeddings(Embeddings):
    """Implementasi LangChain Embeddings berbasis fastembed TextEmbedding."""

    def __init__(self, model_name: str) -> None:
        try:
            from fastembed import TextEmbedding
        except ModuleNotFoundError as exc:
            raise ImportError(
                "fastembed belum terpasang. Jalankan uv sync untuk memasang dependensi."
            ) from exc

        self._model_name = model_name
        self._model = _load_fastembed_model(TextEmbedding, model_name)
        logger.info("Model vektor bawaan FastEmbed sudah dimuat: {}", model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(emb) for emb in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return list(next(iter(self._model.embed([text]))))

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)


__all__ = ["FastEmbedEmbeddings", "_load_fastembed_model"]
