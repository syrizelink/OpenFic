from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.types import ContextMessage
from app.storage.services import agent_rule_service


async def build_rules(db_session: AsyncSession, project_id: str | None = None) -> ContextMessage | None:
    """Membangun potongan konteks p3 Rules: menampilkan semua aturan global dan
    aturan proyek saat ini; daftar kosong mengembalikan None; kegagalan DB
    memunculkan ContextBuildError."""
    try:
        rules = await agent_rule_service.list_all_rules(db_session, project_id)
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
