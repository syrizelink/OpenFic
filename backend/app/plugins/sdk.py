"""Public read-only data facade; plugins receive DTOs, never ORM sessions."""

from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlmodel import col
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.project import Project
from app.storage.models.chapter import Chapter
from app.storage.models.volume import Volume
from app.storage.models.character import Character
from app.storage.models.note import Note
from app.storage.models.world_info import WorldInfo
from app.storage.models.world_info_entry import WorldInfoEntry


class ProjectData:
    def __init__(self, session: AsyncSession, capabilities: Sequence[str]):
        self._session = session
        self._capabilities = frozenset(capabilities)

    def _require(self, capability: str):
        if capability not in self._capabilities:
            raise PermissionError(f"Plugin has not declared {capability}")

    async def list_projects(self) -> list[dict[str, Any]]:
        self._require("projects.read")
        result = await self._session.execute(
            select(col(Project.id), col(Project.title)).order_by(
                col(Project.title), col(Project.id)
            )
        )
        return [dict(row._mapping) for row in result]

    async def project_entities(self, project_id: str) -> dict[str, Any]:
        self._require("project.entities.read")
        project = await self._session.get(Project, project_id)
        if project is None:
            raise ValueError("Project does not exist")
        queries = {
            "chapters": select(
                col(Chapter.id),
                col(Chapter.title),
                col(Chapter.word_count),
                col(Chapter.volume_id),
                col(Chapter.order),
            )
            .where(col(Chapter.project_id) == project_id)
            .order_by(col(Chapter.order), col(Chapter.id)),
            "volumes": select(col(Volume.id), col(Volume.title), col(Volume.order))
            .where(col(Volume.project_id) == project_id)
            .order_by(col(Volume.order)),
            "characters": select(col(Character.id), col(Character.name)).where(
                col(Character.project_id) == project_id
            ),
            "notes": select(col(Note.id), col(Note.title)).where(
                col(Note.project_id) == project_id
            ),
            "world_entries": select(
                col(WorldInfoEntry.id),
                col(WorldInfoEntry.name),
                col(WorldInfoEntry.is_enabled),
            )
            .join(WorldInfo, col(WorldInfoEntry.world_info_id) == col(WorldInfo.id))
            .where(col(WorldInfo.project_id) == project_id),
        }
        entities: dict[str, Any] = {
            "project": {
                "id": project.id,
                "title": project.title,
                "updated_at": project.updated_at.isoformat(),
            }
        }
        for name, query in queries.items():
            rows = await self._session.execute(query)
            entities[name] = [dict(row._mapping) for row in rows]
        return entities


@dataclass(frozen=True)
class PluginContext:
    plugin_id: str
    settings: dict[str, Any] = field(repr=False)
    data: ProjectData
    host: Any = field(default=None, repr=False)
    runtime: dict[str, Any] = field(default_factory=dict, repr=False)
    _private_runtime: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def assets(self):
        from app.plugins.services import PluginAssets

        return PluginAssets(self.host, self.plugin)

    @property
    def plugin(self):
        return self.host.get(self.plugin_id)

    def require(self, capability: str):
        self.data._require(capability)

    async def call(self, method: str, params: dict | None = None):
        """Call the same public, capability-checked SDK used by frontend plugins."""
        from app.plugins.runtime import sdk_call

        return await sdk_call(self, method, params or {})

    @property
    def api(self):
        from app.plugins.gateway import BusinessAPI

        return BusinessAPI(
            self.data._session,
            self.plugin.manifest.capabilities,
            lambda event, data: self.host.emit(event, data, self.plugin_id),
            trace_context=self,
        )

    def resource(self, name: str):
        from app.plugins.gateway import ResourceClient

        return ResourceClient(self.api, name)

    @property
    def chapters(self):
        return self.resource("chapters")

    @property
    def projects(self):
        return self.resource("projects")

    @property
    def notes(self):
        return self.resource("notes")

    @property
    def storage(self):
        from app.plugins.services import PluginStorage

        return PluginStorage(self.host, self.plugin)

    @property
    def secrets(self):
        from app.plugins.services import PluginStorage

        return PluginStorage(self.host, self.plugin, secret=True)

    @property
    def files(self):
        from app.plugins.services import PluginFiles

        return PluginFiles(self.host, self.plugin)

    @property
    def http(self):
        from app.plugins.services import PluginHTTP

        return PluginHTTP(self.plugin, getattr(self.host, "http_transport", None), host=self.host)

    @property
    def models(self):
        from app.plugins.services import PluginModels

        return PluginModels(self)

    @property
    def oauth(self):
        from app.plugins.oauth import PluginOAuth

        return PluginOAuth(self)

    @property
    def agent(self):
        from app.plugins.agent import PluginAgent

        return PluginAgent(self)

    def emit(self, event: str, data: dict):
        self.require("events")
        return self.host.emit(f"plugin.{self.plugin_id}.{event}", data, self.plugin_id)

    def invalidate_ui(self):
        """Notify native views without escaping the plugin event namespace manually."""
        self.require("ui")
        return self.host.emit("ui.invalidate", {}, self.plugin_id)

    def log(self, message: str, level="info"):
        self.host._log(self.plugin_id, "plugin", str(message)[:4000], level)
