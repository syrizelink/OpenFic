import json
from xml.sax.saxutils import escape

from pydantic import BaseModel

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import (
    world_info_entry_repo,
    world_info_repo,
)


class ReadWorldInfoInput(BaseModel):
    pass


@ToolRegistry.register
class ReadWorldInfoTool(AgentTool):
    name: str = "read_world_info"
    description: str = """读取当前项目中的世界书内容。
    
    **世界书的内容**（可能包含）:
    - 关于角色、势力、地点和世界观等设定信息
    - 在使用设定时需要注意的问题
    - 需要遵循的规则，如文风"""
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReadWorldInfoInput

    async def _execute(self) -> str:
        session = await create_session()
        try:
            world_info = await world_info_repo.get_by_project_id(
                session,
                self.project_id,
            )
            if world_info is None:
                return json.dumps({"content": ""}, ensure_ascii=False)

            entries = await world_info_entry_repo.list_enabled_by_world_info(
                session,
                world_info.id,
            )
            entries.sort(key=lambda entry: entry.order)
            return json.dumps(
                {"content": self._format_world_entries(entries)},
                ensure_ascii=False,
            )
        finally:
            await session.close()

    def _format_world_entries(self, entries: list) -> str:
        return "\n".join(
            f"<{self._xml_tag_name(entry.name)}>\n{escape(entry.content)}\n</{self._xml_tag_name(entry.name)}>"
            for entry in entries
        )

    def _xml_tag_name(self, name: str) -> str:
        return name.strip() or "entry"
