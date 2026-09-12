"""Alat Skill: mengaktifkan skill sesuai kebutuhan dan membaca dokumen
referensi."""

from collections.abc import Iterable
from textwrap import dedent

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.agents.definitions import AgentDefinition, load_agent_definition
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.services import skill_service

SKILL_TOOL_NAMES: tuple[str, ...] = ("activate_skill", "reference_skill")


async def skill_tool_names_for_definition(
    definition: AgentDefinition,
    db_session: AsyncSession,
    *,
    referenced_skill_ids: Iterable[str] = (),
    allow_runtime_skill_references: bool = False,
) -> tuple[str, ...]:
    """Mengembalikan nama alat skill hanya bila agent benar-benar memiliki skill
    yang dapat dipakai; jika tidak, kembalikan kosong."""
    normalized_references = {
        skill_id.strip()
        for skill_id in referenced_skill_ids
        if isinstance(skill_id, str) and skill_id.strip()
    }
    if (
        not definition.enabled_skills
        and not normalized_references
        and not allow_runtime_skill_references
    ):
        return ()

    if allow_runtime_skill_references and not definition.enabled_skills and not normalized_references:
        return SKILL_TOOL_NAMES

    available = []
    if definition.enabled_skills:
        available.extend(
            await skill_service.list_enabled_skills_by_ids(
                db_session,
                [skill_id for skill_id in definition.enabled_skills if skill_id],
            )
        )
    if normalized_references:
        global_skills = await skill_service.list_enabled_skills(db_session)
        available.extend(
            skill for skill in global_skills if skill.id.strip() in normalized_references
        )
    return SKILL_TOOL_NAMES if available or allow_runtime_skill_references else ()


class ActivateSkillInput(BaseModel):
    skill_name: str = Field(
        description=(
            "Nama skill yang akan diaktifkan, harus ada di dalam daftar skill yang "
            "tersedia"
        )
    )


class ReferenceSkillInput(BaseModel):
    skill_name: str = Field(
        description="Nama skill, harus ada di dalam daftar skill yang tersedia"
    )
    reference_name: str = Field(
        description=(
            "Nama dokumen referensi, berasal dari daftar ref yang dikembalikan "
            "activate_skill"
        )
    )


def _agent_key_from_state(state: dict) -> str:
    return state.get("active_agent") or state.get("agent_key") or "build"


async def _resolve_authorized_skill(session: AsyncSession, state: dict, skill_name: str):
    normalized = skill_name.strip()
    if not normalized:
        raise ToolExecutionError("Nama skill tidak boleh kosong")

    agent_key = _agent_key_from_state(state)
    definition = await load_agent_definition(session, agent_key)
    available = await skill_service.list_enabled_skills_by_ids(
        session,
        [skill_id for skill_id in definition.enabled_skills if skill_id],
    )
    skill = next(
        (s for s in available if s.name.strip() == normalized or s.id.strip() == normalized),
        None,
    )
    if skill is None:
        referenced_ids = state.get("referenced_skill_ids")
        if isinstance(referenced_ids, (list, tuple, set)) and normalized in referenced_ids:
            globally_enabled = await skill_service.list_enabled_skills(session)
            skill = next((s for s in globally_enabled if s.id.strip() == normalized), None)
        elif isinstance(referenced_ids, (list, tuple, set)):
            globally_enabled = await skill_service.list_enabled_skills(session)
            skill = next(
                (
                    s
                    for s in globally_enabled
                    if s.id.strip() in referenced_ids and s.name.strip() == normalized
                ),
                None,
            )
    if skill is None:
        raise ToolExecutionError(
            f"Skill tidak ada di dalam daftar yang tersedia untuk agen ini: {normalized}"
        )

    return skill


@ToolRegistry.register
class ActivateSkillTool(AgentTool):
    name: str = "activate_skill"
    description: str = dedent("""\
        Mengambil isi lengkap skill yang ditentukan beserta daftar dokumen
        referensinya.
        <available_skills> memuat daftar skill yang tersedia; bila skill yang
        ditentukan tidak ada di dalam daftar itu, permintaan akan ditolak.
    """)
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ActivateSkillInput

    async def _execute(self, skill_name: str) -> str:
        session = await create_session()
        try:
            skill = await _resolve_authorized_skill(session, self._state, skill_name)
            docs = await skill_service.list_reference_docs(session, skill.id)
        finally:
            await session.close()

        body = (skill.content or "").strip()
        references = "\n".join(f"  <ref>{doc.title}</ref>" for doc in docs if doc.title)
        references_block = ""
        if references:
            references_block = f"\n<skill_references>\n{references}\n</skill_references>"
        return f'<skill_content name="{skill.name}">\n{body}{references_block}\n</skill_content>'


@ToolRegistry.register
class ReferenceSkillTool(AgentTool):
    name: str = "reference_skill"
    description: str = dedent("""\
        Membaca isi dokumen referensi tertentu dari sebuah skill.
        Sebelum memakai alat ini, activate_skill harus dijalankan lebih dulu untuk
        mendapatkan reference_name yang sesuai.
    """)
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReferenceSkillInput

    async def _execute(self, skill_name: str, reference_name: str) -> str:
        normalized_ref = reference_name.strip()
        if not normalized_ref:
            raise ToolExecutionError("Nama dokumen referensi tidak boleh kosong")

        session = await create_session()
        try:
            skill = await _resolve_authorized_skill(session, self._state, skill_name)
            docs = await skill_service.list_reference_docs(session, skill.id)
        finally:
            await session.close()

        doc = next((d for d in docs if d.title == normalized_ref), None)
        if doc is None:
            available = ", ".join(d.title for d in docs if d.title) or "tidak ada"
            raise ToolExecutionError(
                f"Dokumen referensi tidak ditemukan: {normalized_ref} "
                f"(yang tersedia: {available})"
            )

        body = (doc.content or "").strip()
        return (
            f'<reference_content skill_name="{skill.name}" reference_name="{doc.title}">\n'
            f"{body}\n"
            f"</reference_content>"
        )
