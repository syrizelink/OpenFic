"""Uji penolakan pemberitahuan galat penyedia sebagai judul sesi.

Latar: penyedia di balik gerbang API dapat menjawab HTTP 200 dengan teks
pemberitahuan sebagai konten completion biasa (tanpa exception, kadang dengan
nol token terpakai). Karena judul sesi hanya dibuat sekali per sesi, teks
semacam itu akan tersimpan permanen sebagai judul bila tidak ditolak.
"""

import pytest

from app.background.jobs.definitions.session_title import (
    _clean_title,
    _looks_like_provider_notice,
)


# Payload yang benar-benar teramati di produksi (2026-09-12, ag/gemini-3.5-flash-extra-low
# menjawab 200 dengan 0 token masuk/keluar dan latensi 516 ms).
PRODUCTION_NOTICE = "Gemini 3.5 Flash is no longer available. Please use a newer model."


@pytest.mark.parametrize(
    "raw",
    [
        PRODUCTION_NOTICE,
        "gemini-3.5-flash is no longer available",
        "This model has been deprecated.",
        "The model was retired on 2026-01-01",
        "model not found: ag/does-not-exist",
        "Model unavailable, please try again later",
        "Rate limit exceeded, try again later",
        "You exceeded your current quota",
        "Insufficient credit to complete this request",
        "Invalid API key provided",
        "401 Unauthorized",
        "Permission denied for this resource",
        "Internal server error",
        "Service unavailable",
        "The engine is currently overloaded",
        "Upstream error from provider",
        '{"error": {"message": "bad things"}}',
        "error: something broke",
        "HTTP 503 returned by gateway",
    ],
)
def test_menolak_pemberitahuan_galat_penyedia(raw: str) -> None:
    assert _looks_like_provider_notice(raw) is True


@pytest.mark.parametrize(
    "raw",
    [
        "Lanjutkan Alur Cerita",
        "Ubah Informasi Latar",
        "Diskusi Persiapan Buku Baru",
        "Menulis Bab 3 Pertempuran Gerbang Utara",
        "Rancang Sistem Sihir Elemental",
        "Perbaiki Alur Bab Pembuka",
        "Bahas Motivasi Tokoh Utama",
        "Ringkas Volume Satu",
    ],
)
def test_menerima_judul_wajar(raw: str) -> None:
    assert _looks_like_provider_notice(raw) is False


def test_teks_kosong_bukan_pemberitahuan_galat() -> None:
    """Judul kosong ditangani cabang lain (_clean_title), bukan detektor ini."""
    assert _looks_like_provider_notice("") is False
    assert _looks_like_provider_notice("   \n  ") is False


def test_deteksi_pada_teks_mentah_bukan_hasil_potong_50_karakter() -> None:
    """Frasa penanda di ujung pesan panjang harus tetap terdeteksi.

    _clean_title memotong ke 50 karakter. Bila pemeriksaan dilakukan setelah
    pemotongan, penanda seperti "is no longer available" akan hilang dan teks
    galat lolos menjadi judul.
    """
    panjang = (
        "Terima kasih atas permintaan Anda yang menarik ini, namun sayangnya model "
        "yang diminta is no longer available"
    )
    assert len(_clean_title(panjang)) == 50
    assert "no longer available" not in _clean_title(panjang)
    assert _looks_like_provider_notice(panjang) is True


def test_penanda_tidak_memicu_pada_kata_indonesia_serupa() -> None:
    """Pemeriksaan berbasis kata utuh tidak boleh kena judul bahasa Indonesia biasa."""
    assert _looks_like_provider_notice("Bahas Error Handling di Bab Dua") is False
    assert _looks_like_provider_notice("Kutipan Quota Panen Desa") is False
