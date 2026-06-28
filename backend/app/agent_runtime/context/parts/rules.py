from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.types import ContextMessage
from app.storage.services import agent_rule_service


async def build_rules(db_session: AsyncSession) -> ContextMessage | None:
    """构建 p3 Rules 上下文片段：列出所有用户规则；空列表返回 None；DB 失败抛 ContextBuildError。"""
    try:
        rules = await agent_rule_service.list_all_rules(db_session)
    except Exception as e:
        raise ContextBuildError("rules", "failed to load rules", cause=e) from e

    if not rules:
        return None

    lines = ["<rules>"]
    for rule in rules:
        lines.append(f"- {rule.content}")
    lines.append("</rules>")

    return ContextMessage(
        role="system",
        content="\n".join(lines),
        metadata={"part": "rules"},
    )
