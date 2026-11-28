from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.core.errors import NotFoundError
from app.storage.models.quick_prompt import QuickPrompt
from app.storage.repos import project_repo


async def list_prompts(session: AsyncSession, project_id: str | None = None) -> list[QuickPrompt]:
    statement = select(QuickPrompt).order_by(QuickPrompt.command, QuickPrompt.id)
    if project_id is not None:
        statement = statement.where(
            or_(col(QuickPrompt.scope) == "global", col(QuickPrompt.project_id) == project_id)
        )
    return list((await session.execute(statement)).scalars().all())


async def get_prompt(session: AsyncSession, prompt_id: str) -> QuickPrompt:
    prompt = await session.get(QuickPrompt, prompt_id)
    if prompt is None:
        raise NotFoundError(f"快捷提示词不存在: {prompt_id}")
    return prompt


async def save_prompt(
    session: AsyncSession,
    *,
    command: str,
    content: str,
    scope: str,
    project_id: str | None,
    prompt: QuickPrompt | None = None,
) -> QuickPrompt:
    if scope == "project" and (
        not project_id or await project_repo.get_by_id(session, project_id) is None
    ):
        raise ValueError("project 作用域必须指定有效的项目")
    if prompt is None:
        prompt = QuickPrompt(command=command, content=content, scope=scope, project_id=project_id)
    else:
        prompt.command = command
        prompt.content = content
        prompt.scope = scope
        prompt.project_id = project_id if scope == "project" else None
    if scope == "global":
        prompt.project_id = None
    session.add(prompt)
    await session.flush()
    return prompt


async def delete_prompt(session: AsyncSession, prompt_id: str) -> None:
    await session.delete(await get_prompt(session, prompt_id))
    await session.flush()
