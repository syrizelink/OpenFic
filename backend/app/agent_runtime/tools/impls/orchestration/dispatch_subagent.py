from __future__ import annotations

import json
from textwrap import dedent
from typing import Any

from pydantic import BaseModel, Field

from app.agent_runtime.agents.definitions import (
    AgentDefinition,
    load_agent_definition,
)
from app.agent_runtime.persistence.child_runs import (
    create_child_run,
    get_child_run_request_by_seq,
    get_running_child_run_request,
    get_waiting_child_run_for_tool_call,
    update_child_run_request_boundaries,
)
from app.agent_runtime.runner.checkpointer import latest_checkpoint_id_for_thread
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.orchestration.common import (
    close_session,
    ensure_child_processing,
    emit_subagent_tool_preview,
    get_configurable,
    make_subagent_runner,
    open_session,
    persist_child_user_message,
    wait_for_request_resolution,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.core.ids import generate_id


MAX_DISPATCHES_PER_TURN = 10


class DispatchSubagentInput(BaseModel):
    agent_type: str = Field(
        description="Tipe Agent khusus yang didelegasikan untuk menangani tugas saat ini",
    )
    description: str = Field(
        min_length=1,
        description=(
            "Deskripsi singkat tugas, harus ringkas dan jelas, maksimal 20 kata"
        ),
    )
    prompt: str = Field(
        min_length=1,
        description=dedent("""\
            Deskripsi tugas yang harus dijalankan Agent, harus mandiri dan jelas,
            minimal mencakup:
            - TASK deskripsi tugas
            - GOAL sasaran atomik
            - EXPECTED OUTCOME hasil yang diserahkan dan kriteria keberhasilan
            - MUST DO pekerjaan yang wajib diselesaikan
            - MUST NOT DO tindakan yang dilarang
            - CONTEXT indeks informasi terkait
        """),
    )
    model_config = {"extra": "forbid"}


def _child_thread_id(parent_thread_id: str, dispatch_id: str) -> str:
    return f"{parent_thread_id}:child:{dispatch_id}"[:128]


@ToolRegistry.register
class DispatchSubagentTool(AgentTool):
    name: str = "dispatch_subagent"
    description: str = dedent("""\
        Mendelegasikan satu Agent baru untuk menangani tugas yang kompleks dan
        bertahap banyak.
        Saat digunakan, parameter agent_type harus ditentukan untuk memilih tipe
        Subagent yang akan didelegasikan.

        Kapan tidak boleh digunakan:
        - Mencari informasi di bab tertentu, di 2-3 bab, atau di latar
        - Tidak ada Agent yang benar-benar cocok dengan tipe tugasnya
        - Saat pengguna secara eksplisit meminta untuk tidak memakai Subagent

        Kapan digunakan:
        - Perlu memproses beberapa tugas independen secara paralel, memakai
          Subagent membantu meningkatkan efisiensi
        - Tugas berkompleksitas tinggi dan sangat spesialis, sehingga perlu Agent
          khusus untuk menanganinya secara terarah
        - Perlu mengisolasi konteks, hanya ingin mengetahui informasi tertentu
          tanpa harus menelusuri seluruh proyek

        Petunjuk penggunaan:
        - Jalankan beberapa Agent secara bersamaan sebisa mungkin untuk
          meningkatkan efisiensi; untuk itu cukup panggil alat ini beberapa kali
          dalam satu putaran pesan
        - Setelah Agent selesai, hasilnya dikembalikan pada hasil alat. Anggap
          secara bawaan bahwa hasil eksekusi Agent tidak terlihat oleh pengguna;
          jika ingin menampilkannya kepada pengguna, keluarkan ringkasan singkat
        - Hasil eksekusi Agent memuat dispatch_id, yang nanti dapat dipakai ulang
          melalui notify_subagent untuk melanjutkan sesi Agent yang sama
        - Hasil eksekusi Agent memuat agent_number; setiap agent memiliki nomor
          unik, dan bila perlu Anda dapat menyebut mereka dengan nomor itu
        - Setiap Agent yang didelegasikan mulai dari konteks baru yang terpisah,
          sehingga Agent tidak mengetahui informasi yang Anda pegang maupun tugas
          yang sudah diselesaikan sebelumnya
        - Saat mendelegasikan Agent, sertakan deskripsi tugas yang rinci, konkret,
          dan dapat dieksekusi di dalam prompt, serta instruksikan dengan jelas
          informasi apa yang harus dikembalikan Agent ketika tugas selesai, karena
          Agent tidak mengetahui maksud pengguna
        - Pada umumnya Anda harus memercayai keluaran Agent
        - Jika deskripsi Agent menyebutkan bahwa mereka sebaiknya digunakan secara
          proaktif, upayakan untuk memakainya tanpa menunggu instruksi eksplisit
          dari pengguna; selain itu gunakan penilaian Anda sendiri
    """)
    access_level: str = "readonly"
    args_schema: type[BaseModel] = DispatchSubagentInput

    async def _load_definition(
        self,
        agent_key: str,
        configurable: dict[str, Any],
    ) -> AgentDefinition:
        session = await open_session(configurable.get("session_factory"))
        try:
            return await load_agent_definition(session, agent_key)
        finally:
            await close_session(session)

    async def _validate_dispatch(
        self,
        agent_key: str,
        configurable: dict[str, Any],
    ) -> None:
        active_agent = self._state.get("active_agent")
        if not isinstance(active_agent, str) or not active_agent:
            raise ToolExecutionError("dispatch_subagent may only be called by primary")

        try:
            primary_def = await self._load_definition(active_agent, configurable)
        except KeyError:
            primary_def = None
        if primary_def is None or primary_def.kind != "primary":
            raise ToolExecutionError("dispatch_subagent may only be called by primary")

        try:
            definition = await self._load_definition(agent_key, configurable)
        except KeyError as exc:
            raise ToolExecutionError(f"unknown subagent: {agent_key}") from exc
        if not definition.enabled or definition.kind != "subagent":
            raise ToolExecutionError(f"agent is not an enabled subagent: {agent_key}")

        if agent_key not in primary_def.delegatable_agents:
            raise ToolExecutionError(
                f"agent '{agent_key}' is not in the delegatable agents whitelist"
            )

    async def _create_child_run(
        self,
        *,
        agent_key: str,
        description: str,
        task: str,
        configurable: dict[str, Any],
        tool_call_id: str,
    ):
        dispatch_id = generate_id()
        parent_thread_id = str(configurable.get("thread_id") or self.session_id)
        child_thread_id = _child_thread_id(parent_thread_id, dispatch_id)
        session = await open_session(configurable.get("session_factory"))
        try:
            return await create_child_run(
                session,
                parent_session_id=self.session_id,
                parent_task_id=str(self._state["task_id"]),
                parent_thread_id=parent_thread_id,
                child_thread_id=child_thread_id,
                agent_key=agent_key,
                dispatch_id=dispatch_id,
                tool_call_id=tool_call_id,
                request={"description": description, "task": task},
                parent_revision_id=self._state.get("current_revision_id")
                if isinstance(self._state.get("current_revision_id"), str)
                else None,
            )
        finally:
            await close_session(session)

    async def _load_waiting_child_run(
        self,
        *,
        configurable: dict[str, Any],
        tool_call_id: str,
    ):
        session = await open_session(configurable.get("session_factory"))
        try:
            return await get_waiting_child_run_for_tool_call(
                session,
                parent_session_id=self.session_id,
                tool_call_id=tool_call_id,
            )
        finally:
            await close_session(session)

    async def _load_initial_request_id(
        self,
        *,
        configurable: dict[str, Any],
        child_run_id: str,
    ) -> str:
        session = await open_session(configurable.get("session_factory"))
        try:
            request_row = await get_child_run_request_by_seq(
                session,
                child_run_id=child_run_id,
                seq=0,
            )
            if request_row is None:
                raise ToolExecutionError("initial subagent request not found")
            return request_row.id
        finally:
            await close_session(session)

    async def _load_running_request_id(
        self,
        *,
        configurable: dict[str, Any],
        child_run_id: str,
    ) -> str:
        session = await open_session(configurable.get("session_factory"))
        try:
            request_row = await get_running_child_run_request(
                session,
                child_run_id=child_run_id,
            )
            if request_row is None:
                raise ToolExecutionError("active subagent request not found")
            return request_row.id
        finally:
            await close_session(session)

    async def _wait_for_assistant_content(
        self,
        *,
        configurable: dict[str, Any],
        child_run_id: str,
        request_id: str,
        runner: Any,
        start_processing: bool = True,
    ) -> str:
        if start_processing:
            await ensure_child_processing(
                parent_session_id=self.session_id,
                child_run_id=child_run_id,
                runner=runner,
                clear_cancelled=False,
            )
        while True:
            resolution = await wait_for_request_resolution(
                session_factory=configurable.get("session_factory"),
                child_run_id=child_run_id,
                request_id=request_id,
            )
            assistant_content = (
                resolution.request.assistant_content
                or resolution.child_run.last_assistant_content
            )
            if not assistant_content:
                raise ToolExecutionError(
                    "subagent turn completed without assistant content"
                )
            return assistant_content

    async def _execute(
        self,
        agent_type: str,
        description: str,
        prompt: str,
    ) -> str:
        configurable = get_configurable(self.config)
        await self._validate_dispatch(agent_type, configurable)
        tool_call_id = self.tool_call_id or generate_id()
        row = await self._load_waiting_child_run(
            configurable=configurable,
            tool_call_id=tool_call_id,
        )
        request_id = None
        if row is not None:
            request_id = await self._load_running_request_id(
                configurable=configurable,
                child_run_id=row.id,
            )
        if row is None:
            row = await self._create_child_run(
                agent_key=agent_type,
                description=description,
                task=prompt,
                configurable=configurable,
                tool_call_id=tool_call_id,
            )
            pre_request_checkpoint_id = await latest_checkpoint_id_for_thread(
                row.child_thread_id
            )
            child_user_message = await persist_child_user_message(
                session_factory=configurable.get("session_factory"),
                child_thread_id=row.child_thread_id,
                task_id=str(self._state["task_id"]),
                project_id=str(self._state["project_id"]),
                content=prompt,
            )
            request_id = await self._load_initial_request_id(
                configurable=configurable,
                child_run_id=row.id,
            )
            session = await open_session(configurable.get("session_factory"))
            try:
                await update_child_run_request_boundaries(
                    session,
                    request_id,
                    child_user_message_id=child_user_message.id,
                    child_user_message_seq=child_user_message.seq,
                    pre_request_checkpoint_id=pre_request_checkpoint_id,
                )
            finally:
                await close_session(session)
        runner = make_subagent_runner(state=self._state, configurable=configurable)
        await runner.publish_parent_subagent_status(row.id)

        base_payload = {
            "dispatch_id": row.dispatch_id,
            "agent_number": (row.metadata_json or {}).get("agent_number"),
        }

        pending_approval = getattr(row, "pending_approval_json", None)
        await emit_subagent_tool_preview(
            configurable=configurable,
            parent_session_id=self.session_id,
            tool_call_id=self.tool_call_id,
            tool_name=self.name,
            tool_args={
                "agent_type": agent_type,
                "description": description,
                "prompt": prompt,
            },
            row=row,
        )
        try:
            assistant_content = await self._wait_for_assistant_content(
                configurable=configurable,
                child_run_id=row.id,
                request_id=request_id or "",
                runner=runner,
                start_processing=not (
                    isinstance(pending_approval, dict) and pending_approval
                ),
            )
        except ToolExecutionError as exc:
            return json.dumps(
                {
                    **base_payload,
                    "error": str(exc),
                },
                ensure_ascii=False,
            )
        payload = {
            **base_payload,
            "result": assistant_content,
        }
        return json.dumps(payload, ensure_ascii=False)
