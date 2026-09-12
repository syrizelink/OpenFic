import json
from textwrap import dedent

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import chapter_summary_repo


class ReadRangeSummariesInput(BaseModel):
    offset: int = Field(description="Offset halaman, dimulai dari 0")
    limit: int = Field(
        description="Jumlah maksimum ringkasan yang dikembalikan kali ini"
    )


@ToolRegistry.register
class ReadRangeSummariesTool(AgentTool):
    name: str = "read_range_summaries"
    description: str = dedent("""\
        Membaca ringkasan jangka panjang, dikembalikan per halaman dan diurutkan naik
        berdasarkan titik awal rentang
        Pembagian rentang:
        - Ringkasan rentang diagregasi dengan satuan tetap setiap 10 bab; rentang yang
          diagregasi selalu bab 1+n*10 sampai bab (n+1)*10, dengan n mewakili
          ringkasan rentang ke-n
        - offset=0,limit=1 -> mengembalikan ringkasan rentang bab 1-10
        - offset=3,limit=5 -> mengembalikan ringkasan rentang bab 31-40, 41-50, 51-60,
          61-70, dan 71-80
    """)
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
