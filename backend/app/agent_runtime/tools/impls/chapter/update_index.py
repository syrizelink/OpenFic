from pydantic import BaseModel

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.background.jobs import service as background_service
from app.retrieval.chapter_index import enqueue_project_index_update
from app.retrieval.index_status import schedule_emit_index_status
from app.storage.database import create_session


class UpdateIndexInput(BaseModel):
    pass


@ToolRegistry.register
class UpdateIndexTool(AgentTool):
    name: str = "update_index"
    description: str = "更新当前项目的章节检索索引（索引所有未就绪章节）。适用于索引非最新时主动更新。"
    access_level: str = "write"
    args_schema: type[BaseModel] = UpdateIndexInput

    async def _execute(self) -> str:
        session = await create_session()
        try:
            result = await enqueue_project_index_update(
                session,
                project_id=self.project_id,
            )
            if result is None:
                await session.commit()
                return "当前项目未启用索引或未配置可用的嵌入模型，无法更新索引。"

            schedule_emit_index_status(session, self.project_id)
            await background_service.commit_and_notify(session)

            if result.enqueued_count == 0:
                return "当前项目的索引已是最新，无需更新。"
            return (
                f"已开始更新当前项目的检索索引，共 {result.enqueued_count} 个章节"
                f"正在排队索引。更新完成后即可检索最新内容。"
            )
        except Exception:
            await background_service.rollback_and_discard(session)
            raise
        finally:
            await session.close()
