import json

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.chapter.refs import VolumeRef, resolve_volume_from_list
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import chapter_repo, volume_repo


class ListChaptersInput(BaseModel):
    volume_ref: VolumeRef = Field(description="Volume sasaran")
    offset: int = Field(description="Offset halaman, dimulai dari 0")
    limit: int = Field(description="Jumlah maksimum bab yang dikembalikan")


class ListChaptersItem(BaseModel):
    order: int
    title: str
    word_count: int


@ToolRegistry.register
class ListChaptersTool(AgentTool):
    name: str = "list_chapters"
    description: str = "Menampilkan semua bab di dalam volume yang ditentukan"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ListChaptersInput

    async def _execute(self, volume_ref: dict, offset: int, limit: int) -> str:
        session = await create_session()
        try:
            ref = VolumeRef.model_validate(volume_ref)
            volumes = await volume_repo.list_by_project(session, self.project_id)
            volume = resolve_volume_from_list(volumes, ref)
            chapters = await chapter_repo.list_metadata_by_volume(
                session, volume.id, offset=offset, limit=limit
            )
            items = [
                ListChaptersItem(
                    order=c.order,
                    title=c.title,
                    word_count=c.word_count,
                ).model_dump()
                for c in chapters
            ]
            return json.dumps(items, ensure_ascii=False)
        finally:
            await session.close()
