"""Versioned, framework-independent plugin package contract."""

from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

API_VERSION = 1
MAX_PACKAGE_BYTES = 20 * 1024 * 1024
MAX_EXPANDED_BYTES = 40 * 1024 * 1024


def safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(
            "Plugin paths must be relative and cannot traverse directories"
        )
    return value


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class View(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    title: str = Field(min_length=1, max_length=80)
    entry: str
    slot: Literal["sidebar.extensions"] = "sidebar.extensions"


class Setting(Contract):
    key: str = Field(pattern=r"^[a-z][a-zA-Z0-9_]{0,63}$")
    label: str = Field(min_length=1, max_length=80)
    type: Literal["string", "boolean", "integer"]
    default: Any
    minimum: int | None = None
    maximum: int | None = None

    def validate_value(self, value: Any) -> Any:
        expected = {"string": str, "boolean": bool, "integer": int}[self.type]
        if type(value) is not expected:
            raise ValueError(f"Invalid setting type: {self.key}")
        if isinstance(value, str) and len(value) > 2000:
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
    backend: str | None = None
    capabilities: list[Literal["projects.read", "project.entities.read"]] = Field(
        default_factory=list
    )
    views: list[View] = Field(default_factory=list, max_length=20)
    settings: list[Setting] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_entries(self):
        if self.backend:
            safe_path(self.backend)
            if not self.backend.endswith(".py"):
                raise ValueError("Backend entry must be a Python file")
        for view in self.views:
            safe_path(view.entry)
            if not view.entry.endswith(".html") or not view.entry.startswith(
                "frontend/"
            ):
                raise ValueError("Views must reference an HTML file under frontend/")
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
