import json

from pydantic import BaseModel

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import volume_repo


class ListVolumesInput(BaseModel):
    pass


class ListVolumesItem(BaseModel):
    order: int
    title: str
    description: str | None
    chapter_count: int


@ToolRegistry.register
class ListVolumesTool(AgentTool):
    name: str = "list_volumes"
    description: str = "列出项目下所有卷，返回卷序号、标题、说明和章节数"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ListVolumesInput

    async def _execute(self) -> str:
        session = await create_session()
        try:
            volumes = await volume_repo.list_by_project(session, self.project_id)
            return json.dumps(
                [
                    ListVolumesItem(
                        order=volume.order,
                        title=volume.title,
                        description=volume.description,
                        chapter_count=volume.chapter_count,
                    ).model_dump()
                    for volume in volumes
                ],
                ensure_ascii=False,
            )
        finally:
            await session.close()
