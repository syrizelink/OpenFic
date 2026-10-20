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


def ui_node(kind, children=None, **props):
    node = {"type": kind, "props": props, "children": children}
    if kind in {"Input", "TextArea"} and props.get("label"):
        return {
            "type": "Flex",
            "props": {"direction": "column", "gap": "2", "minWidth": "0"},
            "children": [
                {
                    "type": "Text",
                    "props": {"size": "2", "weight": "medium"},
                    "children": props["label"],
                },
                node,
            ],
        }
    return node


UI_CSS = """
:scope { --example-accent: var(--accent-9); }
.example-page { width: 100%; max-width: 1100px; margin: 0 auto; min-width: 0; }
.example-panel { padding: 20px; min-width: 0; }
.example-title { color: var(--accent-11); }
.example-actions { flex-wrap: wrap; }
.example-output { display: block; white-space: pre-wrap; overflow-wrap: anywhere; max-height: 24rem; overflow: auto; }
.example-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.example-metric strong { display: block; font-size: 26px; margin-top: 8px; }
.example-table { overflow-x: auto; }
.example-conflict { border: 1px solid var(--orange-7); padding: 12px; border-radius: 8px; }
.example-compact { padding: 8px; }
@media (max-width: 640px) {
  .example-panel { padding: 12px; }
  .example-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .example-actions > button { flex: 1 1 auto; }
}
"""


def ui_button(title, action, **props):
    return ui_node("Button", title, onPress=action, **props)


def ui_row(*children):
    return ui_node(
        "Flex", list(children), gap="3", align="center", className="example-actions"
    )


def ui_panel(*children):
    return ui_node(
        "Card",
        ui_node("Flex", list(children), direction="column", gap="4"),
        className="example-panel",
    )


def ui_status(state):
    return ui_node(
        "Text",
        state.get("status", ""),
        id="status",
        role="status",
        size="2",
        color="gray",
    )


def ui_document(*children, compact=False):
    return {
        "css": UI_CSS,
        "tree": ui_node(
            "Flex",
            list(children),
            direction="column",
            gap="4",
            **{
                "className": "example-page" + (" example-compact" if compact else ""),
            },
        ),
    }


async def ui_state(ctx, params, global_default=False):
    context = params.get("context", {})
    key = (
        "ui:"
        + params.get("viewId", "main")
        + ":"
        + str(context.get("projectId") or "global")
    )
    state = await ctx.storage.get(key, {})
    if "project" not in state:
        projects = await ctx.data.list_projects()
        state["project"] = context.get("projectId") or (
            "" if global_default or not projects else projects[0]["id"]
        )
    return key, state


async def ui_configuration(ctx, state):
    import json

    saved = await config(ctx, {"projectId": state["project"]})
    return {
        "enabled": state.get("enabled", saved.get("enabled", True)),
        "elements": json.loads(
            state.get("elements", json.dumps(saved["elements"], ensure_ascii=False))
        ),
        "rules": json.loads(
            state.get("rules", json.dumps(saved["rules"], ensure_ascii=False))
        ),
    }


async def ui_render(ctx, params):
    import json

    _, state = await ui_state(ctx, params, global_default=True)
    view = params.get("viewId")
    if view == "editor":
        return ui_document(
            ui_row(
                ui_button("读取编辑器", "read", variant="soft"),
                ui_button("撤销", "undo", variant="soft"),
            ),
            ui_node(
                "TextArea",
                label="插入文本",
                value=state.get("text", ""),
                onChange="text",
                rows=2,
            ),
            ui_button("插入并保存", "insert"),
            ui_status(state),
            compact=True,
        )
    configuration = await config(ctx, {"projectId": state["project"]})
    if view == "switches":
        return ui_document(
            ui_node(
                "Flex",
                [
                    ui_node(
                        "Flex",
                        [
                            ui_node(
                                "Switch",
                                checked=bool(item.get("enabled", False)),
                                onCheckedChange="toggle:" + item["id"],
                                label=str(item.get("title") or item["id"]),
                            ),
                            ui_node(
                                "Text", str(item.get("title") or item["id"]), size="2"
                            ),
                        ],
                        gap="2",
                        align="center",
                    )
                    for item in configuration["elements"]
                ],
                wrap="wrap",
                gap="3",
            ),
            ui_status(state),
            compact=True,
        )
    # Keep invalid JSON drafts editable; validation happens when saving or previewing.
    try:
        draft = await ui_configuration(ctx, state)
        items = draft["elements"] if isinstance(draft["elements"], list) else []
    except (ValueError, TypeError):
        items = []
    toggles = [
        ui_node(
            "Flex",
            [
                ui_node(
                    "Checkbox",
                    checked=bool(item.get("enabled", False)),
                    onCheckedChange="draft-toggle:" + item["id"],
                    label=str(item.get("title") or item["id"]),
                ),
                ui_node("Text", str(item.get("title") or item["id"]), size="2"),
            ],
            gap="2",
            align="center",
        )
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
    ]
    preview_result = state.get("preview")
    return ui_document(
        ui_node("Heading", "动态提示词元素", className="example-title"),
        ui_node(
            "Text",
            "规则只影响本次发给模型的上下文，不修改保存的对话。匹配可以读取上下文、最后一条用户消息、指定角色和系统片段。",
            size="2",
            color="gray",
        ),
        ui_panel(
            ui_row(
                ui_node(
                    "ProjectSelector",
                    label="配置范围",
                    placeholder="全局默认",
                    value=state["project"],
                    onChange="project",
                ),
                ui_button("使用全局默认", "global", variant="soft"),
            ),
            ui_row(
                ui_node(
                    "Switch",
                    checked=state.get("enabled", configuration.get("enabled", True)),
                    onCheckedChange="enabled",
                    label="启用动态注入",
                ),
                ui_node("Text", "启用动态注入"),
            ),
            ui_node("Flex", toggles, gap="3", wrap="wrap"),
            ui_node(
                "Grid",
                [
                    ui_node(
                        "TextArea",
                        label="元素定义",
                        value=state.get(
                            "elements",
                            json.dumps(
                                configuration["elements"], ensure_ascii=False, indent=2
                            ),
                        ),
                        onChange="elements",
                        rows=14,
                        resize="vertical",
                        **{"aria-label": "元素定义"},
                    ),
                    ui_node(
                        "TextArea",
                        label="规则定义",
                        value=state.get(
                            "rules",
                            json.dumps(
                                configuration["rules"], ensure_ascii=False, indent=2
                            ),
                        ),
                        onChange="rules",
                        rows=14,
                        resize="vertical",
                    ),
                ],
                columns={"initial": "1", "md": "2"},
                gap="4",
            ),
            ui_row(
                ui_button("保存规则", "save"),
                ui_button("导出配置", "export", variant="soft"),
            ),
        ),
        ui_panel(
            ui_node("Heading", "上下文预览", size="3"),
            ui_node(
                "TextArea",
                label="系统提示词",
                value=state.get("system", "你是一位小说创作助手。"),
                onChange="system",
                rows=3,
            ),
            ui_node(
                "TextArea",
                label="用户消息",
                value=state.get("user", "描写一段梦境中的战斗。"),
                onChange="user",
                rows=3,
            ),
            ui_button("预览注入结果", "preview"),
            ui_status(state),
            ui_node(
                "Text",
                "命中规则："
                + ", ".join(preview_result["matched"])
                + "；启用元素："
                + ", ".join(preview_result["active"])
                if preview_result
                else "尚未预览。",
                id="matched",
                size="2",
            ),
            ui_node(
                "Code",
                json.dumps(preview_result["messages"], ensure_ascii=False, indent=2)
                if preview_result
                else "预览结果将在这里显示。",
                id="output",
                className="example-output",
            ),
        ),
    )


async def ui_action(ctx, params):
    import json

    key, state = await ui_state(ctx, params, global_default=True)
    action = params["id"]
    if action in {"project", "global"}:
        state = {"project": params["value"] if action == "project" else ""}
    elif action in {"enabled", "elements", "rules", "system", "user", "text"}:
        state[action] = params["value"]
        state.pop("preview", None)
    elif action.startswith("toggle:") or action.startswith("draft-toggle:"):
        immediate = action.startswith("toggle:")
        configuration = copy.deepcopy(
            await config(ctx, {"projectId": state["project"]})
            if immediate
            else await ui_configuration(ctx, state)
        )
        item = next(
            (
                item
                for item in configuration["elements"]
                if item["id"] == action.split(":", 1)[1]
            ),
            None,
        )
        if item is None:
            raise ValueError("Unknown element")
        item["enabled"] = bool(params["value"])
        if immediate:
            await save(ctx, {"projectId": state["project"], "config": configuration})
            state["status"] = "已保存，下一次模型请求生效"
            ctx.host.emit("ui.invalidate", {}, ctx.plugin_id)
        else:
            state["elements"] = json.dumps(
                configuration["elements"], ensure_ascii=False, indent=2
            )
    elif action in {"save", "preview", "export"}:
        configuration = validate(await ui_configuration(ctx, state))
        if action == "save":
            await save(ctx, {"projectId": state["project"], "config": configuration})
            state = {**state, "status": "规则已保存，将在下一次模型请求生效"}
            ctx.host.emit("ui.invalidate", {}, ctx.plugin_id)
        elif action == "preview":
            state["preview"] = await preview(
                ctx,
                {
                    "projectId": state["project"],
                    "config": configuration,
                    "messages": [
                        {
                            "role": "system",
                            "content": state.get("system", "你是一位小说创作助手。"),
                            "metadata": {"part": "system_prompt"},
                        },
                        {
                            "role": "user",
                            "content": state.get("user", "描写一段梦境中的战斗。"),
                        },
                    ],
                },
            )
            state["status"] = "预览完成"
        else:
            return {
                "effects": [
                    {
                        "method": "ui.download",
                        "params": {
                            "name": "prompt-elements.json",
                            "text": json.dumps(
                                configuration, ensure_ascii=False, indent=2
                            ),
                            "mime": "application/json",
                        },
                    }
                ]
            }
    elif action == "read":
        return {
            "effects": [{"method": "editor.read", "params": {"summary": True}}],
            "next": "read-result",
        }
    elif action == "read-result":
        data = params["value"][0]
        state["status"] = (
            f"{data['title']} · {data['contentLength']} 字符 · 选择：{data['selection']['text']}"
        )
    elif action == "insert":
        return {
            "effects": [
                {
                    "method": "editor.insert",
                    "discardResult": True,
                    "params": {"text": state.get("text", "")},
                },
                {"method": "editor.save"},
            ],
            "next": "insert-result",
        }
    elif action == "insert-result":
        state["status"] = "已插入并保存"
    elif action == "undo":
        return {
            "effects": [{"method": "editor.undo", "discardResult": True}],
            "next": "undo-result",
        }
    elif action == "undo-result":
        state["status"] = "已撤销，请保存"
    else:
        raise ValueError("Unknown UI action")
    await ctx.storage.set(key, state)


def register(host):
    host.register_command("ui.render", ui_render)
    host.register_command("ui.action", ui_action)
    host.register_hook("context.build", process, priority=100)
    host.register_command("prompt.config", config)
    host.register_command("prompt.save", save)
    host.register_command("prompt.preview", preview)
