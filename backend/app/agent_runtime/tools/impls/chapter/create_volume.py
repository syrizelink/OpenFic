import json
from typing import Any

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
    title: str = Field(description="卷标题")
    description: str | None = Field(
        default=None,
        description="卷说明，可选",
    )


@ToolRegistry.register
class CreateVolumeTool(AgentTool):
    name: str = "create_volume"
    description: str = "创建一个新卷"
    access_level: str = "write"
    args_schema: type[BaseModel] = CreateVolumeInput

    async def build_interrupt_preview(self, args: dict[str, Any]) -> dict | None:
        session = self.get_runtime_db_session()
        title = args.get("title")
        description = args.get("description")
        if (
            session is None
            or not isinstance(title, str)
            or (description is not None and not isinstance(description, str))
        ):
            return None
        max_order = await volume_repo.get_max_order(session, self.project_id)
        return {
            "type": "preview",
            "success": True,
            "reason": "approval_preview",
            "metadata": {
                "volume": {
                    "order": max_order + 1,
                    "title": title,
                    "description": description,
                    "chapter_count": 0,
                }
            },
        }

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
                    "success": True,
                    "metadata": {"volume": serialize_volume(volume)},
                },
                ensure_ascii=False,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
