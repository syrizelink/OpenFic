"""Versioned, framework-independent plugin package contract."""

from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)

from app.plugins.package_builder import (
    safe_path,
    MAX_PACKAGE_BYTES as MAX_PACKAGE_BYTES,
    MAX_EXPANDED_BYTES as MAX_EXPANDED_BYTES,
)

API_VERSION = 1
SDK_VERSION = "2.0.0"
UI_SLOTS = (
    "sidebar.extensions",
    "app.overlay",
    "project.toolbar",
    "editor.toolbar",
    "editor.context",
    "editor.panel",
    "assistant.toolbar",
    "assistant.above-prompt",
    "statusbar",
    "settings.plugins",
    "dashboard",
)
RESOURCE_NAMES = (
    "projects",
    "chapters",
    "volumes",
    "characters",
    "relationships",
    "notes",
    "worldbooks",
    "rules",
    "skills",
    "agents",
    "sessions",
    "tasks",
    "summaries",
    "retrieval",
    "revisions",
    "models",
    "settings",
    "exports",
    "imports",
    "background",
    "providers",
    "prompts",
    "memories",
    "dashboard",
    "audit",
    "tunnels",
)
CAPABILITIES = frozenset(
    [f"{name}.{mode}" for name in RESOURCE_NAMES for mode in ("read", "write")]
    + [
        "project.entities.read",
        "storage",
        "secrets",
        "network",
        "events",
        "ui",
        "ui.overlay",
        "editor.read",
        "editor.write",
        "agent.tools",
        "agent.hooks",
        "agent.graph",
        "agent.models",
        "agent.invoke",
        "files",
        "timers",
    ]
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class View(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    title: str = Field(min_length=1, max_length=80)
    renderer: Literal["iframe", "declarative"] = "iframe"
    entry: str | None = None
    render: str | None = Field(default=None, pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]{0,79}$")
    action: str | None = Field(default=None, pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]{0,79}$")
    slot: str = "sidebar.extensions"
    height: int = Field(default=320, ge=80, le=1600)
    icon: str | None = None
    presentation: Literal["popover", "dialog"] | None = None

    @model_validator(mode="after")
    def known_slot(self):
        if self.slot not in UI_SLOTS:
            raise ValueError(f"Unknown UI slot: {self.slot}")
        if self.icon is not None:
            from .declarative import normalize_icon

            self.icon = normalize_icon(self.icon)
        if self.presentation is not None and self.slot not in {
            "editor.toolbar",
            "editor.context",
            "editor.panel",
        }:
            raise ValueError("presentation is only supported in editor slots")
        if self.renderer == "iframe":
            if not self.entry or self.render or self.action:
                raise ValueError(
                    "Iframe views require entry and cannot bind render/action commands"
                )
            safe_path(self.entry)
            if not self.entry.endswith(".html"):
                raise ValueError("Views must reference an HTML file")
        elif self.entry or not self.render or not self.action:
            raise ValueError(
                "Declarative views require render/action commands and cannot have entry"
            )
        elif self.render.startswith("sdk.") or self.action.startswith("sdk."):
            raise ValueError(
                "Declarative views must bind plugin commands, not SDK methods"
            )
        return self


class Setting(Contract):
    key: str = Field(pattern=r"^[a-z][a-zA-Z0-9_]{0,63}$")
    label: str = Field(min_length=1, max_length=80)
    type: Literal["string", "boolean", "integer", "json", "number"]
    default: Any
    minimum: int | None = None
    maximum: int | None = None
    secret: bool = False
    description: str = ""

    def validate_value(self, value: Any) -> Any:
        if self.type == "json":
            import json

            if len(json.dumps(value, allow_nan=False).encode()) > 256_000:
                raise ValueError(f"Setting is too large: {self.key}")
            return value
        if self.type == "number":
            if type(value) not in (int, float):
                raise ValueError(f"Invalid setting type: {self.key}")
            import math

            if (
                not math.isfinite(value)
                or (self.minimum is not None and value < self.minimum)
                or (self.maximum is not None and value > self.maximum)
            ):
                raise ValueError(f"Setting outside finite bounds: {self.key}")
            return value
        expected = {"string": str, "boolean": bool, "integer": int}[self.type]
        if type(value) is not expected:
            raise ValueError(f"Invalid setting type: {self.key}")
        if isinstance(value, str) and len(value) > 256_000:
            raise ValueError(f"Setting is too long: {self.key}")
        if self.type == "integer":
            if self.minimum is not None and value < self.minimum:
                raise ValueError(f"Setting below minimum: {self.key}")
            if self.maximum is not None and value > self.maximum:
                raise ValueError(f"Setting above maximum: {self.key}")
        return value

    @model_validator(mode="after")
    def validate_default(self):
        self.validate_value(self.default)
        return self


class Manifest(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    name: str = Field(min_length=1, max_length=80)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    api_version: Literal[1]
    description: str = Field(default="", max_length=1000)
    author: str = Field(default="", max_length=100)
    entry: str | None = Field(
        default=None, validation_alias=AliasChoices("entry", "backend")
    )
    resources: list[str] = Field(default_factory=list, max_length=50)
    capabilities: list[str] = Field(default_factory=list)
    views: list[View] = Field(default_factory=list, max_length=60)
    settings: list[Setting] = Field(default_factory=list, max_length=100)
    network_hosts: list[str] = Field(default_factory=list, max_length=50)
    format: Literal["openfic"] = "openfic"
    # Accept metadata from older native exports, but no longer emit it.
    compatibility: dict[str, Any] = Field(default_factory=dict, exclude=True)
    _legacy_resources: bool = PrivateAttr(default=False)

    @model_validator(mode="wrap")
    @classmethod
    def legacy_layout(cls, value, handler):
        # Read old installed manifests and exports without making their layout
        # the convention for newly authored plugins. Always serialize entry/resources.
        legacy = isinstance(value, cls) and value._legacy_resources
        if isinstance(value, dict) and "resources" not in value:
            views = value.get("views", [])
            if "backend" in value or (
                isinstance(views, list)
                and any(
                    isinstance(v, dict)
                    and str(v.get("entry", "")).startswith("frontend/")
                    for v in views
                )
            ):
                value = {**value, "resources": ["frontend"]}
                legacy = True
        result = handler(value)
        result._legacy_resources = legacy
        return result

    def resource_url_name(self, name: str) -> str:
        return name.removeprefix("frontend/") if self._legacy_resources else name

    def resource_name(self, name: str) -> str:
        try:
            self.resource_root(name)
            return name
        except ValueError:
            if not self._legacy_resources:
                raise
            name = "frontend/" + safe_path(name)
            self.resource_root(name)
            return name

    def resource_root(self, name: str) -> str:
        safe_path(name)
        for root in self.resources:
            if name == root or name.startswith(root + "/"):
                return root
        raise ValueError("Path is not a declared public resource")

    def resource_path(self, package, name: str):
        name = self.resource_name(name)
        root = (package / self.resource_root(name)).resolve()
        path = (package / name).resolve()
        if (
            not root.is_relative_to(package.resolve())
            or not path.is_relative_to(root)
            or not path.is_file()
        ):
            raise ValueError("Resource is missing or outside its declared public root")
        return path

    @model_validator(mode="after")
    def validate_entries(self):
        if set(self.capabilities) - CAPABILITIES:
            raise ValueError(
                f"Unknown capabilities: {set(self.capabilities) - CAPABILITIES}"
            )
        if any("/" in host or ":" in host or not host for host in self.network_hosts):
            raise ValueError("Network hosts must be hostnames without scheme or port")
        if self.entry:
            safe_path(self.entry)
            if not self.entry.endswith(".py"):
                raise ValueError("Plugin entry must be a Python file")
        for root in self.resources:
            safe_path(root)
            if any(
                name
                and (
                    name.casefold() == root.casefold()
                    or name.casefold().startswith(root.casefold() + "/")
                )
                for name in (self.entry, "plugin.json", "plugin.dev.json")
            ):
                raise ValueError(
                    "Public resources cannot expose the plugin entry or manifests"
                )
        if len({root.casefold() for root in self.resources}) != len(self.resources):
            raise ValueError("Duplicate public resource root")
        if (
            any(view.renderer == "declarative" for view in self.views)
            and "ui" not in self.capabilities
        ):
            raise ValueError("Declarative views require ui capability")
        if (
            any(view.slot == "app.overlay" for view in self.views)
            and "ui.overlay" not in self.capabilities
        ):
            raise ValueError("Application overlays require ui.overlay capability")
        if any(
            view.slot == "app.overlay" and view.renderer != "declarative"
            for view in self.views
        ):
            raise ValueError("Application overlays currently require declarative UI")
        for view in self.views:
            if view.entry:
                self.resource_root(view.entry)
        for values in (
            [view.id for view in self.views],
            [s.key for s in self.settings],
        ):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate view or setting identifier")
        return self

    def validate_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        definitions = {setting.key: setting for setting in self.settings}
        if values.keys() - definitions.keys():
            raise ValueError("Unknown plugin setting")
        return {
            key: setting.validate_value(values.get(key, setting.default))
            for key, setting in definitions.items()
        }
