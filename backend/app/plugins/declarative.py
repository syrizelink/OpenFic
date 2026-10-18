"""Bounded, data-only UI protocol. No plugin HTML, CSS or JS enters the host DOM."""

import json
from typing import Any

COMPONENTS = frozenset(
    {
        "Box",
        "Text",
        "Button",
        "Input",
        "Select",
        "Code",
        "Markdown",
        "Link",
        "Checkbox",
        "Switch",
        "Separator",
        "Badge",
        "Progress",
        "Svg",
        "Image",
        "Client",
    }
)
PROPS = frozenset(
    {
        "key",
        "children",
        "text",
        "source",
        "label",
        "value",
        "placeholder",
        "disabled",
        "autoFocus",
        "hotkey",
        "onPress",
        "onInput",
        "onSubmit",
        "onSelect",
        "onChange",
        "options",
        "checked",
        "bold",
        "dimColor",
        "color",
        "inverse",
        "wrap",
        "flexDirection",
        "justifyContent",
        "alignItems",
        "gap",
        "marginTop",
        "paddingX",
        "paddingY",
        "padding",
        "borderStyle",
        "borderColor",
        "href",
        "title",
        "max",
        "italic",
        "plain",
    }
)


def validate_document(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Declarative render must return a document object")
    if len(json.dumps(value, allow_nan=False).encode()) > 1024 * 1024:
        raise ValueError("Declarative UI exceeds 1 MiB")
    count = 0

    def node(item, depth=0):
        nonlocal count
        count += 1
        if depth > 32 or count > 4096:
            raise ValueError("Declarative UI exceeds depth/node budget")
        if item is None or isinstance(item, (str, bool, int, float)):
            return item
        if isinstance(item, list):
            return [node(child, depth + 1) for child in item]
        if not isinstance(item, dict) or item.get("type") not in COMPONENTS:
            raise ValueError("Unknown declarative component")
        props = item.get("props", {})
        if not isinstance(props, dict) or props.keys() - PROPS:
            raise ValueError("Unknown declarative component property")
        clean = {}
        for key, prop in props.items():
            if key == "children":
                continue
            if key == "options":
                if (
                    not isinstance(prop, list)
                    or len(prop) > 200
                    or any(
                        not isinstance(p, dict)
                        or not isinstance(p.get("value"), str)
                        or not isinstance(p.get("label", ""), str)
                        for p in prop
                    )
                ):
                    raise ValueError("Invalid Select options")
                clean[key] = [
                    {"value": p["value"], "label": p.get("label", p["value"])}
                    for p in prop
                ]
            elif prop is None or isinstance(prop, (str, bool, int, float)):
                if prop is not None:
                    if key in {
                        "disabled",
                        "autoFocus",
                        "checked",
                        "bold",
                        "dimColor",
                        "inverse",
                        "italic",
                        "plain",
                    } and not isinstance(prop, bool):
                        raise ValueError(f"{key} must be boolean")
                    if key in {
                        "gap",
                        "marginTop",
                        "paddingX",
                        "paddingY",
                        "padding",
                        "max",
                    } and type(prop) not in (int, float):
                        raise ValueError(f"{key} must be a number")
                    if key not in {
                        "value",
                        "disabled",
                        "autoFocus",
                        "checked",
                        "bold",
                        "dimColor",
                        "inverse",
                        "italic",
                        "plain",
                        "gap",
                        "marginTop",
                        "paddingX",
                        "paddingY",
                        "padding",
                        "max",
                    } and not isinstance(prop, str):
                        raise ValueError(f"{key} must be a string")
                clean[key] = prop
            else:
                raise ValueError("UI properties must be scalar values")
        return {
            "type": item["type"],
            "props": clean,
            "children": node(
                item.get("children", props.get("children", [])), depth + 1
            ),
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
