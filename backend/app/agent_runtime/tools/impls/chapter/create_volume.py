import json

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.models.volume import Volume
from app.storage.repos import volume_repo


def serialize_volume(volume: Volume) -> dict[str, int | str | None]:
    return {
        "order": volume.order,
        "title": volume.title,
        "description": volume.description,
        "chapter_count": volume.chapter_count,
    }


class CreateVolumeInput(BaseModel):
    title: str = Field(description="新卷标题")
    description: str | None = Field(
        default=None,
        description="可选的新卷说明",
    )


@ToolRegistry.register
class CreateVolumeTool(AgentTool):
    name: str = "create_volume"
    description: str = "在项目末尾创建一个新卷"
    access_level: str = "write"
    args_schema: type[BaseModel] = CreateVolumeInput

    async def _execute(self, title: str, description: str | None = None) -> str:
        session = await create_session()
        try:
            max_order = await volume_repo.get_max_order(session, self.project_id)
            volume = Volume(
                project_id=self.project_id,
                title=title,
                description=description,
                order=max_order + 1,
                chapter_count=0,
            )
            volume = await volume_repo.create(session, volume)
            await session.commit()
            return json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "revision_id": self._state.get("current_revision_id"),
                    "volume": serialize_volume(volume),
                    "message": "卷已创建",
                },
                ensure_ascii=False,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
