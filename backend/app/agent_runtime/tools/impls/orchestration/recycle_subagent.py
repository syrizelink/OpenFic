from __future__ import annotations

import json
from textwrap import dedent

from pydantic import BaseModel, Field

from app.agent_runtime.persistence.child_runs import recycle_child_run
from app.agent_runtime.runner.checkpointer import delete_checkpoints_for_thread
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.orchestration.common import (
    build_subagent_identity_payload,
    close_session,
    ensure_primary,
    get_configurable,
    make_subagent_runner,
    open_session,
    resolve_child_run,
)
from app.agent_runtime.tools.registry import ToolRegistry


class RecycleSubagentInput(BaseModel):
    dispatch_id: str = Field(
        min_length=1,
        description="ID sesi subagent",
    )
    reason: str = Field(
        default="",
        description=(
            "Opsional, alasan penutupan; dipakai sebagai informasi error/penutup saat "
            "sub-agen didaur ulang, terlihat oleh pengguna, dan harus sesingkat mungkin"
        ),
    )


@ToolRegistry.register
class RecycleSubagentTool(AgentTool):
    name: str = "recycle_subagent"
    description: str = dedent("""\
        Menutup satu sesi Subagent
        Saat digunakan, dispatch_id harus ditentukan untuk memilih sesi yang akan
        ditutup

        Petunjuk penggunaan:
        - Sesi Subagent yang sudah ditutup tidak dapat dipulihkan
        - Tutup Subagent hanya bila tugasnya sudah jelas selesai dan tidak
          diperlukan lagi setelahnya, agar pekerjaan tidak mustahil dilanjutkan
          ketika instruksi berikutnya dari pengguna membutuhkannya
        - Ketika satu kebutuhan sudah selesai ditangani dan pengguna menyatakan
          setuju atau meminta mulai mengerjakan kebutuhan berikutnya, tutup segera
          Subagent yang tidak lagi diperlukan
        - Untuk Subagent yang hanya membaca tanpa melakukan perubahan apa pun,
          menutup sesi umumnya tidak berdampak dan boleh dilakukan setelah tugas
          selesai
        - Jika deskripsi Subagent menyebutkan kapan sebaiknya ia ditutup secara
          proaktif, upayakan untuk mengikutinya; selain itu gunakan penilaian Anda
          sendiri
    """)
    access_level: str = "readonly"
    args_schema: type[BaseModel] = RecycleSubagentInput

    async def _execute(
        self,
        dispatch_id: str,
        reason: str = "",
    ) -> str:
        configurable = get_configurable(self.config)
        await ensure_primary(self._state, configurable.get("session_factory"))
        row = await resolve_child_run(
            parent_session_id=self.session_id,
            session_factory=configurable.get("session_factory"),
            dispatch_id=dispatch_id,
        )
        if not row.is_active:
            return json.dumps(
                {
                    "dispatch_id": row.dispatch_id,
                    **build_subagent_identity_payload(row),
                    "recycled": True,
                },
                ensure_ascii=False,
            )

        await get_agent_run_registry().cancel_child(self.session_id, row.id)

        session = await open_session(configurable.get("session_factory"))
        try:
            recycled = await recycle_child_run(
                session,
                row.id,
                error=reason or None,
            )
        finally:
            await close_session(session)
        await delete_checkpoints_for_thread(recycled.child_thread_id)

        runner = make_subagent_runner(state=self._state, configurable=configurable)
        await runner.publish_parent_subagent_status(recycled.id)
        return json.dumps(
            {
                "dispatch_id": recycled.dispatch_id,
                **build_subagent_identity_payload(recycled),
                "recycled": True,
            },
            ensure_ascii=False,
        )
