from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.agents.definitions import load_agent_definition
from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.graph.state import AgentRuntimeState
from app.storage.services import skill_service


async def _get_enabled_skill_ids_for_agent(
    db_session: AsyncSession,
    agent_name: str,
) -> list[str]:
    try:
        definition = await load_agent_definition(db_session, agent_name)
    except KeyError:
        return []
    return [skill_id for skill_id in definition.enabled_skills if skill_id]


async def build_skills(
    state: AgentRuntimeState,
    agent_name: str,
    db_session: AsyncSession,
) -> ContextMessage | None:
    """构建 Skills 上下文片段：列出 agent 可用技能的名称与简介。"""

    enabled_skill_ids = await _get_enabled_skill_ids_for_agent(db_session, agent_name)

    try:
        available = await skill_service.list_enabled_skills_by_ids(
            db_session,
            enabled_skill_ids,
        )
    except Exception as e:
        raise ContextBuildError("skills", "failed to load enabled skills", cause=e) from e

    if not available:
        return None

    skill_blocks = "\n".join(
        f"<skill>\n  <name>{skill.name}</name>\n  <description>{skill.summary}</description>\n</skill>"
        for skill in available
    )
    content = (
        "<available_skills>\n"
        "The following skills provide specialized instructions for specific tasks.\n"
        "When a task matches a skill's description, call the activate_skill tool with the skill's name to load its full instructions.\n"
        f"{skill_blocks}\n"
        "</available_skills>"
    )

    return ContextMessage(
        role="system",
        content=content,
        metadata={"part": "skills"},
    )