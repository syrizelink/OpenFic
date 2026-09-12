from __future__ import annotations

from textwrap import dedent
from typing import Any

from pydantic import BaseModel

from app.agent_runtime.plan import service as plan_service
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.plan._shared import WritePlanInput
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session


def _todo_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError(f"Tipe parameter Todo tidak didukung: {type(value)!r}")


@ToolRegistry.register
class WritePlanTool(AgentTool):
    name: str = "write_plan"
    description: str = dedent("""\
        Membuat dan memelihara daftar tugas terstruktur untuk sesi saat ini, dipakai
        untuk melacak kemajuan, menata pekerjaan yang kompleks dan bertahap banyak,
        serta menampilkan kemajuan kepada pengguna.
        Saat digunakan, seluruh daftar Todo rencana pada sesi saat ini akan ditimpa,
        karena itu setiap pemanggilan harus menyertakan daftar yang lengkap.

        Kapan digunakan:
        - Tugas memerlukan 3+ langkah atau tindakan yang berbeda (perhatikan, yang
          dimaksud di sini bukan tiga kali pemanggilan alat)
        - Tugas cukup kompleks sehingga perencanaan membuatnya lebih tertata dan
          lebih baik dieksekusi
        - Pengguna memberikan beberapa kebutuhan tugas, atau secara eksplisit meminta
          memakai rencana
        - Menerima kebutuhan baru - uraikan dan catat sebagai daftar Todo
        - Memulai tugas - tandai item Todo saat ini sebagai in_progress sebelum mulai
          mengerjakannya
        - Menyelesaikan tugas - tandai item Todo saat ini sebagai completed, lalu
          perbarui atau tambahkan item lanjutan berdasarkan temuan nyata selama
          pengerjaan

        Kapan tidak boleh digunakan:
        - Tugas tunggal, langsung, dan sederhana yang dapat dikerjakan tanpa
          perencanaan
        - Langkah tugas remeh dan sederhana (<3 langkah)
        - Kebutuhan pengguna bersifat diskusi atau percakapan
        - Rencana tidak memberi nilai bagi penataan tugas saat ini

        Status:
        - pending: menunggu dikerjakan, belum dimulai
        - in_progress: sedang berjalan, saat ini dikerjakan (hanya satu)
        - completed: sudah berhasil diselesaikan

        Prioritas:
        - low: prioritas rendah, boleh ditunda
        - medium: prioritas sedang, ditangani normal
        - high: prioritas tinggi, harus ditangani lebih dulu

        Petunjuk penggunaan:
        - Perbarui status tugas secara real-time, langsung sebelum memulai atau
          menyelesaikan sebuah tugas; jangan menyisakannya untuk pembaruan massal di
          akhir
        - Tandai completed hanya setelah pekerjaan pada item Todo benar-benar selesai
          (termasuk verifikasi dan persetujuan, bila perlu)
        - Pada satu waktu tandai tepat satu item Todo dengan status in_progress
        - Bila tugas terhambat atau selesai sebagian, item Todo yang terhambat boleh
          tetap in_progress; perbarui rencana lanjutan agar sesuai kondisi saat ini
          lalu lanjutkan
        - Setiap item Todo harus berupa subtugas mandiri yang konkret dan dapat
          dikerjakan
    """)
    access_level: str = "write"
    args_schema: type[BaseModel] = WritePlanInput

    async def _execute(self, todos: list[Any]) -> str:
        session = await create_session()
        try:
            snapshot = await plan_service.write_plan(
                session,
                runtime_state=self._state,
                todos=[_todo_payload(todo) for todo in todos],
            )
            await session.commit()
            return plan_service.format_plan_todos(snapshot["todos"])
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
