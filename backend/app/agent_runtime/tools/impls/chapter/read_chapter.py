from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.chapter.refs import (
    ChapterRef,
    VolumeRef,
    resolve_chapter_from_list,
    resolve_volume_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import chapter_repo, volume_repo


class ReadChapterInput(BaseModel):
    volume_ref: VolumeRef = Field(description="目标卷")
    chapter_ref: ChapterRef = Field(description="卷内的目标章节")


class ReadChapterOutput(BaseModel):
    order: int
    title: str
    content: str
    word_count: int


def format_chapter_content_with_line_numbers(content: str) -> str:
    if not content:
        return ""
    return "\n".join(
        f"{line_number}|{line}"
        for line_number, line in enumerate(content.splitlines(), start=1)
    )


@ToolRegistry.register
class ReadChapterTool(AgentTool):
    name: str = "read_chapter"
    description: str = (
        "读取指定卷内章节的完整内容"
        "必须使用 volume_ref 指定目标卷，并使用 chapter_ref 指定目标章节"
        "返回的 content 会按章节内从 1 开始的行号格式化，每个原始换行都会拆分为单独一行，格式为 `行号|内容`"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReadChapterInput

    async def _execute(self, volume_ref: dict, chapter_ref: dict) -> str:
        volume = VolumeRef.model_validate(volume_ref)
        ref = ChapterRef.model_validate(chapter_ref)
        session = await create_session()
        try:
            volumes = await volume_repo.list_by_project(session, self.project_id)
            resolved_volume = resolve_volume_from_list(volumes, volume)
            chapters = await chapter_repo.list_by_volume(session, resolved_volume.id)
            match = resolve_chapter_from_list(chapters, ref)
            return ReadChapterOutput(
                order=match.order,
                title=match.title,
                content=format_chapter_content_with_line_numbers(match.content),
                word_count=match.word_count,
            ).model_dump_json()
        finally:
            await session.close()
