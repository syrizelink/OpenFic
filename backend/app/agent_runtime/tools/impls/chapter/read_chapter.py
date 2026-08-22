from time import perf_counter

from loguru import logger
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
        started_at = perf_counter()
        volume = VolumeRef.model_validate(volume_ref)
        ref = ChapterRef.model_validate(chapter_ref)
        logger.info(
            "read_chapter_start project_id={} volume_ref={} chapter_ref={}",
            self.project_id,
            volume_ref,
            chapter_ref,
        )
        session = self.get_runtime_db_session()
        owns_session = session is None
        if session is None:
            session_started_at = perf_counter()
            session = await create_session()
            session_create_ms = int((perf_counter() - session_started_at) * 1000)
        else:
            session_create_ms = 0
        try:
            volume_query_started_at = perf_counter()
            volumes = await volume_repo.list_by_project(session, self.project_id)
            volume_query_ms = int((perf_counter() - volume_query_started_at) * 1000)
            logger.info(
                "read_chapter_volume_query project_id={} volume_count={} "
                "session_create_ms={} query_ms={}",
                self.project_id,
                len(volumes),
                session_create_ms,
                volume_query_ms,
            )
            resolved_volume = resolve_volume_from_list(volumes, volume)
            chapter_query_started_at = perf_counter()
            chapters = await chapter_repo.list_by_volume(session, resolved_volume.id)
            chapter_query_ms = int((perf_counter() - chapter_query_started_at) * 1000)
            loaded_content_chars = sum(len(chapter.content or "") for chapter in chapters)
            logger.info(
                "read_chapter_chapter_query project_id={} volume_id={} chapter_count={} "
                "loaded_content_chars={} query_ms={}",
                self.project_id,
                resolved_volume.id,
                len(chapters),
                loaded_content_chars,
                chapter_query_ms,
            )
            match = resolve_chapter_from_list(chapters, ref)
            format_started_at = perf_counter()
            content = format_chapter_content_with_line_numbers(match.content)
            format_ms = int((perf_counter() - format_started_at) * 1000)
            result = ReadChapterOutput(
                order=match.order,
                title=match.title,
                content=content,
                word_count=match.word_count,
            ).model_dump_json()
            logger.info(
                "read_chapter_end project_id={} volume_id={} chapter_id={} chapter_order={} "
                "result_chars={} format_ms={} total_ms={}",
                self.project_id,
                resolved_volume.id,
                match.id,
                match.order,
                len(result),
                format_ms,
                int((perf_counter() - started_at) * 1000),
            )
            return result
        except Exception:
            logger.exception(
                "read_chapter_error project_id={} total_ms={}",
                self.project_id,
                int((perf_counter() - started_at) * 1000),
            )
            raise
        finally:
            if owns_session:
                await session.close()
