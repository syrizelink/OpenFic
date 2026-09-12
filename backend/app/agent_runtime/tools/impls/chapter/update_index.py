from pydantic import BaseModel

from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolFailure, serialize_tool_failure
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
    description: str = (
        "Memperbarui indeks vektor bab (mengindeks semua bab yang belum siap), "
        "dipakai untuk memperbarui secara proaktif saat indeks tidak mutakhir."
    )
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
                return serialize_tool_failure(
                    ToolFailure(
                        code="dependency_unavailable",
                        message=(
                            "Proyek saat ini belum mengaktifkan indeks atau belum "
                            "mengonfigurasi model embedding yang dapat dipakai, "
                            "sehingga indeks tidak dapat diperbarui."
                        ),
                        trace={"source": "chapter_index"},
                    )
                )

            schedule_emit_index_status(session, self.project_id)
            await background_service.commit_and_notify(session)

            if result.enqueued_count == 0:
                return (
                    "Indeks proyek saat ini sudah mutakhir, tidak perlu diperbarui."
                )
            return (
                f"Pembaruan indeks pencarian proyek saat ini sudah dimulai, "
                f"{result.enqueued_count} bab sedang menunggu diindeks. "
                f"Setelah pembaruan selesai, isi terbaru dapat langsung dicari."
            )
        except Exception:
            await background_service.rollback_and_discard(session)
            raise
        finally:
            await session.close()
