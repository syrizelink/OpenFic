from textwrap import dedent

from pydantic import BaseModel, Field

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.chapter.refs import (
    ChapterRef,
    VolumeRef,
    resolve_chapter_from_list,
    resolve_volume_from_list,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session
from app.storage.repos import chapter_repo, volume_repo


class ReadChapterInput(BaseModel):
    volume_ref: VolumeRef = Field(description="Volume sasaran")
    chapter_ref: ChapterRef = Field(description="Bab sasaran di dalam volume")


class ReadChapterOutput(BaseModel):
    order: int
    title: str
    content: str
    word_count: int


def format_chapter_content_with_line_numbers(content: str) -> str:
    if not content:
        return ""
    return "\n".join(
        f"{line_number}|{line}"
        for line_number, line in enumerate(content.splitlines(), start=1)
    )


@ToolRegistry.register
class ReadChapterTool(AgentTool):
    name: str = "read_chapter"
    description: str = dedent("""\
        Membaca isi lengkap sebuah bab di dalam volume yang ditentukan
        volume_ref harus dipakai untuk menentukan volume sasaran, dan chapter_ref
        untuk menentukan bab sasaran
        content yang dikembalikan adalah hasil pemformatan dengan nomor baris yang
        dimulai dari 1 di dalam bab; isi aslinya tidak memuat penanda nomor baris
        Setiap baris baru pada isi asli dipecah menjadi satu baris tersendiri dan
        diberi penanda nomor baris dengan format `nomor_baris|isi`
    """)
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ReadChapterInput

    async def _execute(self, volume_ref: dict, chapter_ref: dict) -> str:
        volume = VolumeRef.model_validate(volume_ref)
        ref = ChapterRef.model_validate(chapter_ref)
        session = await create_session()
        try:
            volumes = await volume_repo.list_by_project(session, self.project_id)
            resolved_volume = resolve_volume_from_list(volumes, volume)
            matched = await chapter_repo.get_by_volume_ref(
                session,
                resolved_volume.id,
                ref_type=ref.type,
                ref_value=ref.value,
            )
            match = resolve_chapter_from_list([matched] if matched is not None else [], ref)
            return ReadChapterOutput(
                order=match.order,
                title=match.title,
                content=format_chapter_content_with_line_numbers(match.content),
                word_count=match.word_count,
            ).model_dump_json()
        finally:
            await session.close()
