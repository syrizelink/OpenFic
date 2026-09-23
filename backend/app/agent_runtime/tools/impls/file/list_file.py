import json

from pydantic import BaseModel
from sqlalchemy import select
from sqlmodel import col

from app.agent_runtime.persistence.model import AgentAttachment
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session


def _attachment_session_id(tool: AgentTool) -> str:
    parent_session_id = tool.runtime_state.get("parent_session_id")
    return parent_session_id if isinstance(parent_session_id, str) and parent_session_id else tool.session_id


class ListFileInput(BaseModel):
    """列出附件不需要额外参数。"""



@ToolRegistry.register
class ListFileTool(AgentTool):
    name: str = "list_file"
    description: str = "列出当前 Agent 会话中的所有附件，仅返回附件基本信息，不返回文件内容"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ListFileInput

    async def _execute(self) -> str:
        session = await create_session()
        try:
            result = await session.execute(
                select(AgentAttachment)
                .where(col(AgentAttachment.session_id) == _attachment_session_id(self))
                .order_by(col(AgentAttachment.created_at), col(AgentAttachment.id))
            )
            return json.dumps(
                [
                    {
                        "id": attachment.id,
                        "file_name": attachment.file_name,
                        "mime_type": attachment.mime_type,
                        "size_bytes": attachment.size_bytes,
                        "content_length": attachment.content_length,
                        "line_count": attachment.line_count,
                    }
                    for attachment in result.scalars()
                ],
                ensure_ascii=False,
            )
        finally:
            await session.close()
