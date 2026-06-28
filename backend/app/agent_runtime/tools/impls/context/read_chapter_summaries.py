import json

from pydantic import BaseModel, Field, model_validator

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import chapter_repo, chapter_summary_repo


class ReadChapterSummariesInput(BaseModel):
    offset: int | None = Field(default=None, description="分页偏移，从0开始")
    limit: int | None = Field(default=None, description="本次返回的最大摘要数")
    orders: list[int] | None = Field(
        default=None,
        description="按精确章节order读取摘要；当同时提供offset/limit时忽略该字段",
    )

    @model_validator(mode="after")
    def validate_query(self) -> "ReadChapterSummariesInput":
        has_page = self.offset is not None or self.limit is not None
        if has_page and (self.offset is None or self.limit is None):
            raise ValueError("offset 和 limit 必须同时传入")
        if not has_page and self.orders is None:
            raise ValueError("必须提供 offset/limit 或 orders")
        return self


@ToolRegistry.register
class ReadChapterSummariesTool(AgentTool):
    name: str = "read_chapter_summaries"
    description: str = """读取章节摘要
    
    章节摘要是一个章节剧情的概括和总结"""
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReadChapterSummariesInput

    async def _execute(
        self,
        offset: int | None = None,
        limit: int | None = None,
        orders: list[int] | None = None,
    ) -> str:
        session = await create_session()
        try:
            chapters = await self._load_target_chapters(
                session,
                offset=offset,
                limit=limit,
                orders=orders or [],
            )
            chapter_ids = [chapter.id for chapter in chapters]
            summaries = await chapter_summary_repo.list_chapter_summaries_by_chapter_ids(
                session,
                chapter_ids,
                ready_only=True,
            )
            summary_by_chapter_id = {summary.chapter_id: summary for summary in summaries}
            payload = [
                {
                    "order": chapter.order,
                    "title": chapter.title,
                    "summary": summary.summary,
                }
                for chapter in chapters
                if (summary := summary_by_chapter_id.get(chapter.id)) is not None
            ]
            return json.dumps({"summaries": payload}, ensure_ascii=False)
        finally:
            await session.close()

    async def _load_target_chapters(
        self,
        session,
        *,
        offset: int | None,
        limit: int | None,
        orders: list[int],
    ) -> list:
        if offset is not None and limit is not None:
            return await chapter_repo.list_by_project_page(
                session,
                self.project_id,
                offset=offset,
                limit=limit,
            )

        chapters = await chapter_repo.list_by_project(session, self.project_id)
        chapter_by_order = {chapter.order: chapter for chapter in chapters}
        return [
            chapter_by_order[order]
            for order in orders
            if order in chapter_by_order
        ]
