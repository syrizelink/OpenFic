# -*- coding: utf-8 -*-
"""Uji toleransi skema alat ``ask_user``.

Regresi yang dijaga: pada 12:27:35 di produksi, model memanggil ``ask_user``
dengan ``description`` dan ``options`` tetapi tanpa ``title``. Skema lama
menolaknya, alat gagal total, lalu agent berhenti memakai alat dan hanya
membalas prosa. Payload di ``test_payload_produksi_yang_dulu_gagal`` adalah
salinan persis dari panggilan yang gagal itu.
"""

import pytest
from pydantic import ValidationError

from app.agent_runtime.tools.impls.interaction.ask_user import (
    AskUserInput,
    Question,
    QuestionOption,
)


def _one(payload: dict) -> Question:
    return AskUserInput.model_validate({"questions": [payload]}).questions[0]


def test_payload_produksi_yang_dulu_gagal() -> None:
    question = _one(
        {
            "description": (
                "Untuk memastikan makalah yang dibuat tepat sasaran, topik "
                "spesifik manakah yang Anda maksud dengan 'anslop ai'?"
            ),
            "options": [
                {
                    "label": "Unsloth AI (Direkomendasikan)",
                    "description": "Framework open-source fine-tuning LLM.",
                },
                {
                    "label": "AI Slop",
                    "description": "Konten berkualitas rendah hasil AI generatif.",
                },
                {
                    "description": "Pengembang model Claude.",
                    "label": "Anthropic AI",
                },
            ],
        }
    )
    assert question.title.startswith("Untuk memastikan makalah")
    # Teks dipindah ke title, tidak digandakan pada description.
    assert question.description == ""
    assert [option.label for option in question.options] == [
        "Unsloth AI (Direkomendasikan)",
        "AI Slop",
        "Anthropic AI",
    ]


def test_bentuk_lengkap_tidak_berubah() -> None:
    question = _one(
        {
            "title": "Pilih genre?",
            "description": "Rincian tambahan",
            "options": [{"label": "Fantasi", "description": "Dunia sihir"}],
        }
    )
    assert question.title == "Pilih genre?"
    assert question.description == "Rincian tambahan"
    assert len(question.options) == 1


def test_title_saja_tanpa_opsi() -> None:
    question = _one({"title": "Pertanyaan terbuka?"})
    assert question.title == "Pertanyaan terbuka?"
    assert question.options == []


@pytest.mark.parametrize("alias", ["question", "text", "prompt", "label"])
def test_alias_teks_dipromosikan_ke_title(alias: str) -> None:
    assert _one({alias: "Pilih genre?"}).title == "Pilih genre?"


def test_title_hanya_spasi_diganti_description() -> None:
    question = _one({"title": "   ", "description": "Pilih genre?"})
    assert question.title == "Pilih genre?"


def test_opsi_boleh_tanpa_description() -> None:
    question = _one({"title": "T", "options": [{"label": "A"}]})
    assert question.options[0] == QuestionOption(label="A", description="")


def test_tanpa_teks_apa_pun_tetap_ditolak() -> None:
    """Toleransi tidak boleh berubah menjadi menerima pertanyaan tanpa isi."""
    with pytest.raises(ValidationError) as excinfo:
        _one({"options": [{"label": "A", "description": "d"}]})
    assert excinfo.value.errors()[0]["loc"] == ("questions", 0, "title")


def test_daftar_pertanyaan_kosong_tetap_ditolak() -> None:
    with pytest.raises(ValidationError):
        AskUserInput.model_validate({"questions": []})
