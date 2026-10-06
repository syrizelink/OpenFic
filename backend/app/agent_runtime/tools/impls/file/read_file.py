from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlmodel import col

from app.agent_runtime.persistence.model import AgentAttachment
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.file.list_file import _attachment_session_id
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session


class ReadFileInput(BaseModel):
    file_id: str = Field(min_length=1, description="要读取的附件 ID")
    offset: int = Field(ge=0, description="内容行偏移，从 0 开始")
    limit: int = Field(gt=0, le=20_000, description="最多读取的行数")


@ToolRegistry.register
class ReadFileTool(AgentTool):
    name: str = "read_file"
    description: str = "读取指定附件的文本内容，必须同时设置 file_id、offset 和 limit"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReadFileInput

    async def _execute(self, file_id: str, offset: int, limit: int) -> str:
        session = await create_session()
        try:
            result = await session.execute(
                select(AgentAttachment).where(
                    col(AgentAttachment.id) == file_id,
                    col(AgentAttachment.session_id) == _attachment_session_id(self),
                )
            )
            attachment = result.scalar_one_or_none()
            if attachment is None:
                raise ToolExecutionError("附件不存在或不属于当前会话")
            if attachment.content is None:
                raise ToolExecutionError("该附件没有可读取的文本内容")
            lines = attachment.content.splitlines(keepends=True)
            content = "".join(lines[offset : offset + limit])
            return f"[{attachment.file_name}]\n\n{content}"
        finally:
            await session.close()
