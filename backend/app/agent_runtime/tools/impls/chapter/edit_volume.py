import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.chapter.create_volume import serialize_volume
from app.agent_runtime.tools.impls.chapter.refs import VolumeRef, resolve_volume_from_list
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import volume_repo


class EditVolumeInput(BaseModel):
    volume_ref: VolumeRef = Field(description="目标卷")
    new_title: str | None = Field(
        default=None,
        description="卷标题",
    )
    new_description: str | None = Field(
        default=None,
        description="卷说明",
    )

    @field_validator("new_description", mode="after")
    @classmethod
    def check_edit_fields(cls, v, info):
        if info.data.get("new_title") is None and v is None:
            raise ValueError("new_title 和 new_description 必填其中一个")
        return v


@ToolRegistry.register
class EditVolumeTool(AgentTool):
    name: str = "edit_volume"
    description: str = "编辑指定卷的标题或说明"
    access_level: str = "write"
    args_schema: type[BaseModel] = EditVolumeInput

    async def _execute(
        self,
        volume_ref: dict,
        new_title: str | None = None,
        new_description: str | None = None,
    ) -> str:
        session = await create_session()
        try:
            volume = resolve_volume_from_list(
                await volume_repo.list_by_project(session, self.project_id),
                VolumeRef.model_validate(volume_ref),
            )
            if new_title is not None:
                volume.title = new_title
            if new_description is not None:
                volume.description = new_description
            volume.updated_at = datetime.now(UTC)
            volume = await volume_repo.update_volume(session, volume)
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
