"""Versioned SDK gateway to existing validated business routes, not raw SQL writes.

The catalogue is generated from the same APIRoutes used for execution. Every
operation carries a resource capability, including nested project routes.
"""

import base64
import importlib
from copy import copy
from contextvars import ContextVar
from functools import lru_cache
from typing import Any
from urllib.parse import unquote

import httpx
from fastapi import FastAPI
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.routing import Match, compile_path

from app.storage.database import get_session

ROUTERS = {
    "projects": ["projects"],
    "chapters": ["chapters", "chapter_context"],
    "volumes": ["volumes"],
    "notes": ["notes"],
    "characters": ["characters"],
    "worldbooks": ["world_info", "world_info_entries"],
    "rules": ["agent_rules"],
    "skills": ["skills", "skill_reference_docs"],
    "agents": ["agent_definitions"],
    "sessions": ["agent_runtime"],
    "tasks": ["tasks"],
    "retrieval": ["retrieval_index"],
    "models": ["models"],
    "settings": ["settings"],
    "exports": ["chapter_exports"],
    "imports": ["import_router"],
    "background": ["background"],
    "providers": ["model_providers", "model_provider_catalog"],
    "prompts": ["prompt_chains"],
    "memories": ["agent_memories"],
    "dashboard": ["dashboard"],
    "audit": ["audit"],
    "tunnels": ["tunnels"],
}

_gateway_session: ContextVar[AsyncSession] = ContextVar("plugin_gateway_session")


async def scoped_session():
    yield _gateway_session.get()


@lru_cache(maxsize=1)
def build_gateway() -> tuple[FastAPI, list[tuple[APIRoute, str]]]:
    app = FastAPI()
    app.dependency_overrides[get_session] = scoped_session
    from app.api.exceptions import register_exception_handlers

    register_exception_handlers(app)
    operations = []
    for resource, modules in ROUTERS.items():
        for name in modules:
            try:
                module = importlib.import_module(f"app.api.routers.{name}")
            except ModuleNotFoundError as error:
                if error.name == f"app.api.routers.{name}":
                    continue
                raise
            for router_name in ("router", "global_router"):
                router = getattr(module, router_name, None)
                if router is None:
                    continue
                prefix = "/agent" if name == "agent_runtime" else ""
                app.include_router(router, prefix=prefix)
                for original_route in router.routes:
                    route = original_route
                    if isinstance(route, APIRoute):
                        if prefix:
                            route = copy(route)
                            route.path = prefix + route.path
                            (
                                route.path_regex,
                                route.path_format,
                                route.param_convertors,
                            ) = compile_path(route.path)
                        actual = resource
                        for keyword, category in [
                            ("relationships", "relationships"),
                            ("summaries", "summaries"),
                            ("revisions", "revisions"),
                        ]:
                            if keyword in route.path:
                                actual = category
                        operations.append((route, actual))
    return app, operations


class BusinessAPI:
    def __init__(self, session: AsyncSession, capabilities, emit=None):
        self.session = session
        self.capabilities = frozenset(capabilities)
        self.emit = emit

    async def request(
        self, method: str, path: str, *, json=None, query=None, form=None, files=None
    ) -> Any:
        method = method.upper()
        if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
            raise ValueError("Unsupported API method")
        if (
            not path.startswith("/")
            or path.startswith("//")
            or any(c in unquote(path) for c in ("..", "\\", "?", "#", "\x00"))
        ):
            raise ValueError("SDK paths must be canonical local paths")
        app, operations = build_gateway()
        scope = {"type": "http", "path": path, "method": method, "root_path": ""}
        resource = next(
            (r for route, r in operations if route.matches(scope)[0] == Match.FULL),
            None,
        )
        if resource is None:
            raise ValueError("Operation is not available through the SDK")
        capability = resource + (".read" if method == "GET" else ".write")
        if capability not in self.capabilities:
            raise PermissionError(f"Plugin has not declared {capability}")

        from app.plugins.host import active_host

        current_host = active_host()
        if current_host and current_host.application:
            app.state = current_host.application.state
        uploaded = None
        if files:
            uploaded = [
                (
                    f["field"],
                    (
                        f["name"],
                        base64.b64decode(f["base64"], validate=True),
                        f.get("mime", "application/octet-stream"),
                    ),
                )
                for f in files
            ]
        token = _gateway_session.set(self.session)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://plugin-sdk"
            ) as client:
                response = await client.request(
                    method, path, json=json, params=query, data=form, files=uploaded
                )
        finally:
            _gateway_session.reset(token)
        if response.status_code >= 400:
            raise ValueError(
                f"SDK {method} {path}: {response.status_code} {response.text[:1000]}"
            )
        if method != "GET":
            await self.session.commit()
            if self.emit:
                self.emit(
                    "data.changed",
                    {"resource": resource, "path": path, "method": method},
                )
            from app.plugins.runtime import dispatch

            try:
                await dispatch(
                    "data.changed",
                    {"resource": resource, "path": path, "method": method},
                    self.session,
                )
            except Exception:
                # The business write has committed; notification failure must
                # not look like a failed write and invite duplicate retries.
                pass
        if not response.content:
            return None
        if "json" in response.headers.get("content-type", ""):
            return response.json()
        return {
            "base64": base64.b64encode(response.content).decode(),
            "mime": response.headers.get("content-type"),
            "filename": response.headers.get("content-disposition"),
        }

    @staticmethod
    def catalogue():
        app, operations = build_gateway()
        return {
            "openapi": app.openapi(),
            "operations": [
                {
                    "path": route.path,
                    "methods": sorted(route.methods or []),
                    "capability": resource,
                    "summary": route.summary or route.name,
                }
                for route, resource in operations
            ],
        }


class ResourceClient:
    """Convenience methods; uncommon actions use request with the catalogue path."""

    def __init__(self, api: BusinessAPI, resource: str):
        self.api, self.resource = api, resource

    async def list(self, project_id=None, **query):
        path = (
            f"/projects/{project_id}/{self.resource}"
            if project_id
            else f"/{self.resource}"
        )
        return await self.api.request("GET", path, query=query)

    async def get(self, entity_id: str):
        return await self.api.request("GET", f"/{self.resource}/{entity_id}")

    async def create(self, values: dict, project_id=None):
        path = (
            f"/projects/{project_id}/{self.resource}"
            if project_id
            else f"/{self.resource}"
        )
        return await self.api.request(
            "POST",
            path,
            **({"form": values} if self.resource == "projects" else {"json": values}),
        )

    async def update(self, entity_id: str, values: dict):
        return await self.api.request(
            "PATCH", f"/{self.resource}/{entity_id}", json=values
        )

    async def delete(self, entity_id: str):
        return await self.api.request("DELETE", f"/{self.resource}/{entity_id}")
