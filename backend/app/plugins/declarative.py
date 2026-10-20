"""Serializable native UI protocol, shared with the frontend component registry."""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOGUE = json.loads(Path(__file__).with_name("ui-catalog.json").read_text())
ICON_NAMES = {name.replace("-", "").lower(): name for name in CATALOGUE["lucideIcons"]}


def normalize_icon(value: str) -> str:
    if not isinstance(value, str) or value.replace("-", "").lower() not in ICON_NAMES:
        raise ValueError("Unknown Lucide icon: " + str(value))
    return ICON_NAMES[value.replace("-", "").lower()]


BREAKPOINTS = {"initial", "xs", "sm", "md", "lg", "xl"}
UNSUPPORTED = {"Svg", "Image", "Client"}


def component_definition(
    source: str, key: str, definition: dict
) -> tuple[str, str, dict]:
    inherited = {
        **CATALOGUE["common"],
        **(CATALOGUE["radixCommon"] if source == "radix" else {}),
    }
    return source, key, {**definition, "props": {**inherited, **definition["props"]}}


@lru_cache(maxsize=512)
def resolve_component(name: str) -> tuple[str, str, dict]:
    if name in CATALOGUE["project"]:
        return component_definition("project", name, CATALOGUE["project"][name])
    target = CATALOGUE["aliases"].get(name, name)
    for prefix, source in (("Project.", "project"), ("Radix.", "radix")):
        if target.startswith(prefix):
            key = target.removeprefix(prefix)
            definition = CATALOGUE[source].get(key)
            if definition is not None:
                return component_definition(source, key, definition)
            break
    else:
        for source in ("project", "radix"):
            if target in CATALOGUE[source]:
                return component_definition(source, target, CATALOGUE[source][target])
    if target in UNSUPPORTED:
        return "unsupported", target, {"props": {}}
    raise ValueError("Unknown declarative component: " + name)


def validate_property(name: str, value: Any, spec: dict) -> Any:
    kind = spec["type"]
    if value is None:
        return value
    if spec.get("responsive") and isinstance(value, dict):
        if not value or value.keys() - BREAKPOINTS:
            raise ValueError("Invalid responsive breakpoints: " + name)
        return {
            k: validate_property(name, v, {**spec, "responsive": False})
            for k, v in value.items()
        }
    if kind == "icon":
        return normalize_icon(value)
    if kind in {"string", "event"}:
        if not isinstance(value, str):
            raise ValueError(name + " must be a string")
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError(name + " must be boolean")
    elif kind == "number":
        if type(value) not in (int, float):
            raise ValueError(name + " must be a number")
    elif kind == "enum":
        if value not in spec["values"] or not any(
            type(value) is type(v) for v in spec["values"]
        ):
            # Legacy numeric gaps use the existing 4px spacing unit.
            if name != "gap" or type(value) not in (int, float):
                raise ValueError("Invalid " + name)
    elif kind == "spacing":
        if not (
            type(value) in (int, float)
            or isinstance(value, str)
            and value in [str(i) for i in range(10)]
        ):
            raise ValueError("Invalid spacing: " + name)
    elif kind in {"strings", "numbers"}:
        expected = str if kind == "strings" else (int, float)
        if (
            not isinstance(value, list)
            or len(value) > 200
            or any(not isinstance(v, expected) or isinstance(v, bool) for v in value)
        ):
            raise ValueError("Invalid array: " + name)
    elif kind == "style":
        if not isinstance(value, dict) or len(value) > 128:
            raise ValueError("style must be a bounded property object")
        for key, item in value.items():
            if (
                not re.fullmatch(r"(?:--[\w-]+|[a-zA-Z][\w-]*)", key)
                or type(item) not in (str, int, float)
                and item is not None
            ):
                raise ValueError("Invalid CSS property: " + key)
            if key.lower() in {"behavior", "mozbinding"}:
                raise ValueError("Unsupported CSS property")
    elif kind == "options":
        if not isinstance(value, list) or len(value) > 200:
            raise ValueError("Invalid Select options")
        allowed = {
            "value",
            "label",
            "description",
            "disabled",
            "labelColor",
            "fontFamily",
            "separatorAfter",
        }
        for option in value:
            if (
                not isinstance(option, dict)
                or option.keys() - allowed
                or not isinstance(option.get("value"), str)
            ):
                raise ValueError("Invalid Select options")
            for key, item in option.items():
                validate_property(
                    key,
                    item,
                    {
                        "type": "boolean"
                        if key in {"disabled", "separatorAfter"}
                        else "string"
                    },
                )
        return [{"label": option["value"], **option} for option in value]
    elif kind != "json":
        raise ValueError("Unknown UI property kind")
    return value


def validate_document(value: Any, *, capabilities: list[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Declarative render must return a document object")
    if len(json.dumps(value, allow_nan=False).encode()) > 1024 * 1024:
        raise ValueError("Declarative UI exceeds 1 MiB")
    css = value.get("css", "")
    if not isinstance(css, str) or len(css.encode()) > 65536:
        raise ValueError("CSS must be a string no larger than 64 KiB")
    count = 0

    def node(item, depth=0, ancestors=()):
        nonlocal count
        count += 1
        if depth > 32 or count > 4096:
            raise ValueError("Declarative UI exceeds depth/node budget")
        if item is None or isinstance(item, (str, bool, int, float)):
            return item
        if isinstance(item, list):
            return [node(child, depth + 1, ancestors) for child in item]
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            raise ValueError("Unknown declarative component")
        source, name, definition = resolve_component(item["type"])
        if capabilities is not None and set(definition.get("capabilities", [])) - set(
            capabilities
        ):
            raise ValueError(
                name + " requires " + ", ".join(definition["capabilities"])
            )
        family, _, part = name.partition(".")
        if (
            source == "radix"
            and part
            and part != "Root"
            and family
            in {
                "Select",
                "Tabs",
                "Dialog",
                "AlertDialog",
                "Popover",
                "HoverCard",
                "DropdownMenu",
                "ContextMenu",
                "RadioGroup",
                "RadioCards",
                "CheckboxGroup",
                "CheckboxCards",
                "SegmentedControl",
                "TextField",
            }
            and family + ".Root" not in ancestors
        ):
            raise ValueError(name + " requires " + family + ".Root")
        props = item.get("props", {})
        if not isinstance(props, dict):
            raise ValueError("UI props must be an object")
        clean = {}
        for key, prop in props.items():
            if key == "children":
                continue
            spec = definition["props"].get(key)
            if re.fullmatch(r"(?:aria|data)-[a-z][a-z0-9-]*", key):
                spec = {"type": "json"}
                if isinstance(prop, (dict, list)):
                    raise ValueError("DOM attributes must be scalar")
            if spec is None:
                raise ValueError("Unknown declarative component property: " + key)
            clean[key] = validate_property(key, prop, spec)
        if source == "project" and name == "Icon" and not clean.get("name"):
            raise ValueError("Icon requires a Lucide name")
        if name == "Select.Item" and not clean.get("value"):
            raise ValueError("Select.Item requires a nonempty value")
        children = item.get("children", props.get("children", []))
        if clean.get("asChild"):
            child = (
                children[0]
                if isinstance(children, list) and len(children) == 1
                else children
            )
            if not isinstance(child, dict):
                raise ValueError("asChild requires a single component child")
        return {
            "type": item["type"],
            "props": clean,
            "children": node(children, depth + 1, (*ancestors, name)),
        }

    entries = value.get("trees", [{"component": "View", "tree": value.get("tree")}])
    if not isinstance(entries, list) or len(entries) > 60:
        raise ValueError("Invalid declarative surfaces")
    trees = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("component", "View") not in {
            "View",
            "AbovePrompt",
            "Pane",
            "Spinner",
        }:
            raise ValueError("Invalid declarative surface")
        trees.append(
            {
                "component": str(entry.get("component", "View"))[:80],
                "requestId": str(entry.get("requestId", ""))[:128],
                "tree": node(entry.get("tree")),
            }
        )
    panes = value.get("panes", [])
    commands = value.get("commands", [])
    if (
        not isinstance(panes, list)
        or not isinstance(commands, list)
        or len(panes) > 60
        or len(commands) > 100
        or any(
            not isinstance(p, dict)
            or not isinstance(p.get("id"), str)
            or not isinstance(p.get("title", ""), str)
            for p in panes
        )
        or any(
            not isinstance(p, dict) or not isinstance(p.get("name"), str)
            for p in commands
        )
    ):
        raise ValueError("Invalid declarative controls")
    return {
        "version": 1,
        "css": css,
        "trees": trees,
        "panes": [
            {
                "id": str(p["id"])[:128],
                "title": str(p.get("title", ""))[:200],
                "focus": bool(p.get("focus")),
                "closeOnEscape": bool(p.get("closeOnEscape")),
            }
            for p in panes
        ],
        "commands": [{"name": str(p["name"])[:128]} for p in commands],
    }
