import json
from textwrap import dedent
from typing import Any

from pydantic import BaseModel, Field, model_validator
from langgraph.types import interrupt

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry


class QuestionOption(BaseModel):
    label: str = Field(
        description="Teks tampilan opsi, harus ringkas dan jelas"
    )
    description: str = Field(default="", description="Keterangan opsi")


class Question(BaseModel):
    title: str = Field(description="Pertanyaan yang lengkap")
    description: str = Field(
        default="",
        description="Keterangan tambahan, opsional",
    )
    options: list[QuestionOption] = Field(
        default_factory=list,
        description="Pilihan yang tersedia, opsional",
    )

    @model_validator(mode="before")
    @classmethod
    def _tolerate_missing_title(cls, data: Any) -> Any:
        """Menerima pertanyaan yang hanya membawa teks pada field lain.

        Model kerap mengirim ``description`` (atau ``question``/``text``) tanpa
        ``title`` karena ketiganya sama-sama berisi kalimat pertanyaan. Menolak
        panggilan seperti itu membuat alat gagal total, dan agent lalu berhenti
        memakai alat sama sekali. Selama masih ada satu kalimat yang bisa
        ditampilkan, pertanyaan tetap dapat disajikan kepada pengguna.
        """
        if not isinstance(data, dict):
            return data
        if str(data.get("title") or "").strip():
            return data
        for alias in ("question", "text", "prompt", "label", "description"):
            candidate = data.get(alias)
            if isinstance(candidate, str) and candidate.strip():
                promoted = dict(data)
                promoted["title"] = candidate.strip()
                if alias == "description":
                    promoted["description"] = ""
                return promoted
        return data


class AskUserInput(BaseModel):
    questions: list[Question] = Field(
        min_length=1,
        description="Daftar pertanyaan",
    )

@ToolRegistry.register
class AskUserTool(AgentTool):
    name: str = "ask_user"
    description: str = dedent("""\
        Gunakan alat ini saat mengajukan pertanyaan kepada pengguna.

        Kapan digunakan:
        - Mengumpulkan preferensi atau kebutuhan pengguna
        - Memperjelas instruksi yang ambigu
        - Mengambil keputusan tentang rencana implementasi selama pengerjaan

        Petunjuk penggunaan:
        - Tidak boleh ada saling ketergantungan antar pertanyaan dalam satu kumpulan
          yang sama (bila ada ketergantungan, tanyakan secara bertahap)
        - Setiap pertanyaan dapat menyediakan opsi untuk memandu pilihan pengguna;
          opsi yang Anda sarankan harus ditempatkan pertama dan diberi akhiran
          `(Direkomendasikan)`
        - Baik opsi diberikan maupun tidak, sistem akan otomatis menambahkan opsi
          `masukkan jawaban sendiri` kepada pengguna, karena itu saat mengajukan
          pertanyaan terbuka jangan menyertakan opsi `lainnya` atau opsi cadangan
          serupa
    """)
    access_level: str = "readonly"
    execute_during_prepare: bool = True
    emit_prepare_events: bool = True
    args_schema: type[BaseModel] = AskUserInput

    async def _execute(self, questions: list[Question]) -> str:
        payload = {
            "type": "ask_user",
            "questions": [question.model_dump(mode="json") for question in questions],
        }
        response = interrupt(payload)
        if isinstance(response, dict) and response.get("skipped") is True:
            return json.dumps(
                {
                    "type": "control",
                    "success": False,
                    "status": "user_skipped",
                    "message": "Pengguna mengabaikan pertanyaan",
                },
                ensure_ascii=False,
            )
        answers = response.get("answer") if isinstance(response, dict) else None
        return json.dumps(answers if isinstance(answers, list) else [], ensure_ascii=False)
