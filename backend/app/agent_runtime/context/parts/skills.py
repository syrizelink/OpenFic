from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.agents.definitions import load_agent_definition
from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.graph.state import AgentRuntimeState
from app.storage.models.skill import Skill
from app.storage.services import skill_service


async def _get_enabled_skill_ids_for_agent(
    db_session: AsyncSession,
    agent_name: str,
) -> list[str]:
    try:
        definition = await load_agent_definition(db_session, agent_name)
    except KeyError:
        return []
    return [skill_id for skill_id in definition.enabled_skill_ids if skill_id]


async def build_skills(
    state: AgentRuntimeState,
    agent_name: str,
    db_session: AsyncSession,
) -> ContextMessage | None:
    """构建 p4 Skills 上下文片段：列出 agent 可用与已激活的技能。"""

    enabled_skill_ids = await _get_enabled_skill_ids_for_agent(db_session, agent_name)

    try:
        available = await skill_service.list_enabled_skills_by_skill_ids(
            db_session,
            enabled_skill_ids,
        )
    except Exception as e:
        raise ContextBuildError("skills", "failed to load enabled skills", cause=e) from e

    installed_ids: list[str] = state.get("installed_skill_ids") or []
    installed: list[Skill] = []
    if installed_ids:
        try:
            installed = await skill_service.list_skills_by_skill_ids(db_session, installed_ids)
        except Exception as e:
            raise ContextBuildError("skills", "failed to load installed skills", cause=e) from e

    if not available and not installed:
        return None

    sections: list[str] = []
    if available:
        lines = ["## 可用技能"]
        for sk in available:
            lines.append(f"- `{sk.skill_id}` — {sk.name}：{sk.summary}")
        sections.append("\n".join(lines))

    if installed:
        lines = ["## 已激活技能"]
        for sk in installed:
            lines.append(f"### {sk.skill_id} {sk.name}")
            lines.append(sk.content or "")
        sections.append("\n".join(lines))

    body = "\n\n".join(sections)
    content = f"<skills>\n{body}\n</skills>"

    return ContextMessage(
        role="system",
        content=content,
        metadata={"part": "skills"},
    )
