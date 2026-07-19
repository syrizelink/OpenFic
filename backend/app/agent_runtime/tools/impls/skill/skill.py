"""Skill 工具：按需激活技能与读取参考文档。"""

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
) -> tuple[str, ...]:
    """当 agent 存在实际可用技能时，才返回 skill 工具名；否则返回空。"""
    if not definition.enabled_skills:
        return ()
    available = await skill_service.list_enabled_skills_by_ids(
        db_session,
        [skill_id for skill_id in definition.enabled_skills if skill_id],
    )
    return SKILL_TOOL_NAMES if available else ()


class ActivateSkillInput(BaseModel):
    skill_name: str = Field(description="要激活的技能名称，必须在可用技能列表中")


class ReferenceSkillInput(BaseModel):
    skill_name: str = Field(description="技能名称，必须在可用技能列表中")
    reference_name: str = Field(description="参考文档名称，来自 activate_skill 返回的 ref 列表")


def _agent_key_from_state(state: dict) -> str:
    return state.get("active_agent") or state.get("agent_key") or "primary"


async def _resolve_authorized_skill(session: AsyncSession, state: dict, skill_name: str):
    normalized = skill_name.strip()
    if not normalized:
        raise ToolExecutionError("技能名称不能为空")

    agent_key = _agent_key_from_state(state)
    definition = await load_agent_definition(session, agent_key)
    available = await skill_service.list_enabled_skills_by_ids(
        session,
        [skill_id for skill_id in definition.enabled_skills if skill_id],
    )
    skill = next((s for s in available if s.name == normalized), None)
    if skill is None:
        raise ToolExecutionError(f"技能不在该智能体的可用列表中: {normalized}")

    return skill


@ToolRegistry.register
class ActivateSkillTool(AgentTool):
    name: str = "activate_skill"
    description: str = (
        "获取指定技能的完整内容与参考文档列表。"
        "技能名称必须来自上下文中可用技能列表。"
        "返回 SKILL.md 正文及可用的参考文档名称。"
    )
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
    description: str = (
        "读取指定技能的某个参考文档内容。"
        "reference_name 来自 activate_skill 返回的 skill_references 中的 ref 字段。"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReferenceSkillInput

    async def _execute(self, skill_name: str, reference_name: str) -> str:
        normalized_ref = reference_name.strip()
        if not normalized_ref:
            raise ToolExecutionError("参考文档名称不能为空")

        session = await create_session()
        try:
            skill = await _resolve_authorized_skill(session, self._state, skill_name)
            docs = await skill_service.list_reference_docs(session, skill.id)
        finally:
            await session.close()

        doc = next((d for d in docs if d.title == normalized_ref), None)
        if doc is None:
            available = ", ".join(d.title for d in docs if d.title) or "无"
            raise ToolExecutionError(
                f"参考文档不存在: {normalized_ref}（可用: {available}）"
            )

        body = (doc.content or "").strip()
        return (
            f'<reference_content skill_name="{skill.name}" reference_name="{doc.title}">\n'
            f"{body}\n"
            f"</reference_content>"
        )
