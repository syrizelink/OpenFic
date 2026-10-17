"""Deterministic prompt elements and contextual rules. Never mutates saved history."""

import copy
import time

import regex

DEFAULT_ELEMENTS = [
    {
        "id": "consistency",
        "title": "人物一致性",
        "enabled": True,
        "role": "system",
        "position": "prepend",
        "text": "保持人物动机、已知事实与当前世界设定一致。",
    },
    {
        "id": "combat",
        "title": "战斗场景细节",
        "enabled": False,
        "role": "system",
        "position": "append",
        "text": "描写战斗时明确空间位置、动作因果和感官细节，避免空泛形容。",
    },
    {
        "id": "dream",
        "title": "梦境叙事",
        "enabled": False,
        "role": "system",
        "position": "append",
        "text": "这是梦境场景，允许不可靠感知，但保持情感线索连贯。",
    },
]
DEFAULT_RULES = [
    {
        "id": "combat-detection",
        "enabled": True,
        "priority": 10,
        "conditions": [
            {
                "source": "last_user",
                "mode": "regex",
                "pattern": "战斗|打斗|combat|battle",
                "caseSensitive": False,
            }
        ],
        "actions": [{"type": "element.set", "element": "combat", "enabled": True}],
    },
    {
        "id": "dream-detection",
        "enabled": True,
        "priority": 20,
        "conditions": [{"source": "context", "mode": "contains", "pattern": "梦境"}],
        "actions": [{"type": "element.set", "element": "dream", "enabled": True}],
    },
]


def validate(config):
    if (
        not isinstance(config, dict)
        or not isinstance(config.get("elements"), list)
        or not isinstance(config.get("rules"), list)
    ):
        raise ValueError("配置必须包含 elements 和 rules 数组")
    if len(config["elements"]) > 100 or len(config["rules"]) > 100:
        raise ValueError("最多 100 个元素和 100 条规则")
    ids = set()
    for element in config["elements"]:
        if not element.get("id") or element["id"] in ids:
            raise ValueError("元素 ID 必须唯一")
        ids.add(element["id"])
        if element.get("role", "system") not in {"system", "user", "assistant"}:
            raise ValueError("Unsupported element role")
        if (
            not isinstance(element.get("text", ""), str)
            or len(element.get("text", "")) > 100000
        ):
            raise ValueError("元素正文过长")
    for rule in config["rules"]:
        for condition in rule.get("conditions", []):
            pattern = condition.get("pattern", "")
            if not isinstance(pattern, str) or len(pattern) > 1000:
                raise ValueError("匹配模式过长")
            if condition.get("mode") == "regex":
                regex.compile(pattern)
        for action in rule.get("actions", []):
            if action.get("type") not in {
                "element.set",
                "element.text",
                "inject",
                "replace",
                "remove",
                "section.hide",
            }:
                raise ValueError("Unsupported action: " + str(action.get("type")))
            if action.get("regex"):
                regex.compile(action.get("pattern", ""))
    return config


async def config(ctx, params):
    project = params.get("projectId") or ctx.runtime.get("project_id")
    if project:
        value = await ctx.storage.get("config:" + project)
        if value is not None:
            return value
    return await ctx.storage.get(
        "config",
        {"elements": DEFAULT_ELEMENTS, "rules": DEFAULT_RULES, "enabled": True},
    )


async def save(ctx, params):
    value = validate(params["config"])
    project = params.get("projectId")
    if project:
        await ctx.projects.get(project)
    await ctx.storage.set("config:" + project if project else "config", value)
    return value


def text_content(message):
    value = message.get("content", "")
    if isinstance(value, str):
        return value
    return (
        "\n".join(block.get("text", "") for block in value if isinstance(block, dict))
        if isinstance(value, list)
        else ""
    )


def source_text(name, messages, event):
    if name == "last_user":
        return next(
            (text_content(m) for m in reversed(messages) if m.get("role") == "user"), ""
        )
    if name in {"user", "assistant", "system", "tool"}:
        return "\n".join(text_content(m) for m in messages if m.get("role") == name)
    if name.startswith("section:"):
        return "\n".join(
            text_content(m)
            for m in messages
            if (m.get("metadata") or {}).get("part") == name[8:]
        )
    if name == "project":
        return str(event.get("projectId", ""))
    if name == "agent":
        return str(event.get("agent", ""))
    return "\n".join(text_content(m) for m in messages)


def match(condition, messages, event):
    text = source_text(condition.get("source", "context"), messages, event)[-500000:]
    pattern = condition.get("pattern", "")
    mode = condition.get("mode", "contains")
    if mode == "regex":
        found = bool(
            regex.search(
                pattern,
                text,
                flags=0 if condition.get("caseSensitive", False) else regex.IGNORECASE,
                timeout=0.05,
            )
        )
    else:
        if not condition.get("caseSensitive", False):
            text, pattern = text.casefold(), pattern.casefold()
        found = {
            "contains": lambda: pattern in text,
            "equals": lambda: pattern == text,
            "startsWith": lambda: text.startswith(pattern),
            "endsWith": lambda: text.endswith(pattern),
        }.get(mode, lambda: False)()
    return not found if condition.get("negate", False) else found


def template(text, messages, event):
    variables = {
        "last_user": source_text("last_user", messages, event),
        "projectId": str(event.get("projectId") or ""),
        "agent": str(event.get("agent") or ""),
        "sessionId": str(event.get("sessionId") or ""),
    }
    for key, value in variables.items():
        text = text.replace("${" + key + "}", value)
    return text


def apply(configuration, event):
    messages = copy.deepcopy(event.get("messages", []))
    elements = copy.deepcopy(configuration["elements"])
    trace = []
    if not configuration.get("enabled", True):
        return {"messages": messages, "matched": [], "active": [], "trace": []}
    original = copy.deepcopy(messages)
    extra = []
    for rule in sorted(configuration["rules"], key=lambda r: r.get("priority", 0)):
        if not rule.get("enabled", True):
            continue
        checks = [match(c, original, event) for c in rule.get("conditions", [])]
        matched = any(checks) if rule.get("match", "all") == "any" else all(checks)
        if not matched:
            continue
        trace.append(
            {"rule": rule.get("id", "unnamed"), "actions": len(rule.get("actions", []))}
        )
        for action in rule.get("actions", []):
            kind = action["type"]
            if kind in {"element.set", "element.text"}:
                for element in elements:
                    if element["id"] == action.get("element"):
                        if kind == "element.set":
                            element["enabled"] = bool(action.get("enabled", True))
                        else:
                            element["text"] = str(action.get("text", ""))
            elif kind == "inject":
                extra.append(
                    {"id": "rule:" + str(rule.get("id")), "enabled": True, **action}
                )
            else:
                selected = []
                for message in messages:
                    if (
                        action.get("roles")
                        and message.get("role") not in action["roles"]
                    ):
                        selected.append(message)
                        continue
                    if kind == "section.hide":
                        if (message.get("metadata") or {}).get("part") == action.get(
                            "section"
                        ):
                            continue
                    elif kind == "replace" and isinstance(message.get("content"), str):
                        if action.get("regex"):
                            message["content"] = regex.sub(
                                action.get("pattern", ""),
                                action.get("replacement", ""),
                                message["content"],
                                timeout=0.05,
                            )
                        else:
                            message["content"] = message["content"].replace(
                                action.get("pattern", ""), action.get("replacement", "")
                            )
                    elif kind == "remove" and match(
                        {
                            "source": "context",
                            "pattern": action.get("pattern", ""),
                            "mode": action.get("mode", "contains"),
                        },
                        [message],
                        event,
                    ):
                        continue
                    selected.append(message)
                messages = selected
        if rule.get("stop", False):
            break
    active = []
    for element in [*elements, *extra]:
        if not element.get("enabled", True):
            continue
        text = template(element.get("text", ""), original, event)
        if not text:
            continue
        active.append(element["id"])
        message = {
            "role": element.get("role", "system"),
            "content": text,
            "metadata": {"part": "plugin_element", "element": element["id"]},
        }
        position = element.get("position", "append")
        if position == "prepend":
            messages.insert(0, message)
        elif position in {"before_last_user", "after_last_user"}:
            index = next(
                (
                    i
                    for i in reversed(range(len(messages)))
                    if messages[i]["role"] == "user"
                ),
                len(messages),
            )
            messages.insert(
                index
                + (1 if position == "after_last_user" and index < len(messages) else 0),
                message,
            )
        else:
            if message["role"] == "system":
                index = next(
                    (i for i, m in enumerate(messages) if m.get("role") != "system"),
                    len(messages),
                )
                messages.insert(index, message)
            else:
                messages.append(message)
    return {
        "messages": messages,
        "matched": [t["rule"] for t in trace],
        "active": active,
        "trace": trace,
    }


async def preview(ctx, params):
    configuration = validate(params.get("config") or await config(ctx, params))
    event = {
        "projectId": params.get("projectId"),
        "agent": params.get("agent", "build"),
        "messages": params.get("messages", []),
    }
    return apply(configuration, event)


async def process(ctx, event, next):
    result = apply(await config(ctx, {"projectId": event.get("projectId")}), event)
    if result["active"] or result["matched"]:
        ctx.emit(
            "prompt.applied",
            {
                "projectId": event.get("projectId"),
                "active": result["active"],
                "matched": result["matched"],
                "time": time.time(),
            },
        )
    return await next({**event, "messages": result["messages"]})


def register(host):
    host.register_hook("context.build", process, priority=100)
    host.register_command("prompt.config", config)
    host.register_command("prompt.save", save)
    host.register_command("prompt.preview", preview)
