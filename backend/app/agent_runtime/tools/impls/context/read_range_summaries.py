import json

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import chapter_summary_repo


class ReadRangeSummariesInput(BaseModel):
    offset: int = Field(description="分页偏移，从0开始")
    limit: int = Field(description="本次返回的最大摘要数")


@ToolRegistry.register
class ReadRangeSummariesTool(AgentTool):
    name: str = "read_range_summaries"
    description: str = """读取长期摘要，按区间起点升序分页返回。
    
    注意，区间摘要是每10个章节为单位聚合的，如：
    - offset=0, limit=1 → 返回第1-10章的区间摘要
    - offset=3, limit=5 → 返回第31-40章、41-50章、51-60章、61-70章、71-80章的区间摘要
    
    区间的划分是固定的，这意味着被聚合的摘要区间始终是1+n*10章到(n+1)*10章，其中n代表第n个区间摘要
    """
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReadRangeSummariesInput

    async def _execute(self, offset: int, limit: int) -> str:
        session = await create_session()
        try:
            summaries = await chapter_summary_repo.list_long_term_summaries_by_project(
                session,
                self.project_id,
                ready_only=True,
            )
            summaries.sort(key=lambda item: item.start_order or 0)
            page = summaries[offset : offset + limit]
            payload = [
                {
                    "start_order": summary.start_order,
                    "end_order": summary.end_order,
                    "summary": summary.summary,
                }
                for summary in page
            ]
            return json.dumps({"summaries": payload}, ensure_ascii=False)
        finally:
            await session.close()
