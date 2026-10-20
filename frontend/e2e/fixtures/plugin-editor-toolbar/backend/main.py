"""Installed through the real package API for toolbar layout and bridge tests."""


def node(kind, children=None, **props):
    return {"type": kind, "props": props, "children": children}


async def render(ctx, params):
    state = await ctx.storage.get("state", {})
    return {
        "css": ".toolbar-glyph { color: var(--accent-11); }",
        "tree": node(
            "Box",
            [
                node(
                    "Icon",
                    name="cloud-upload",
                    size=24,
                    strokeWidth=1.5,
                    label="声明式云图标",
                    className="toolbar-glyph",
                ),
                node("Text", str(params["context"].get("kind")), id="kind"),
                node(
                    "Text",
                    str(
                        params["context"].get("chapterId")
                        or params["context"].get("noteId")
                    ),
                    id="entity",
                ),
                node(
                    "TextArea",
                    label="浮层输入",
                    value=state.get("draft", ""),
                    onChange="draft",
                ),
                node("Button", "插入选区", onPress="insert"),
                node("Text", state.get("status", ""), id="status"),
            ],
            gap=2,
        ),
    }


async def action(ctx, params):
    state = await ctx.storage.get("state", {})
    if params["id"] == "draft":
        state["draft"] = params["value"]
    elif params["id"] == "insert":
        return {
            "effects": [
                {
                    "method": "editor.insert",
                    "params": {"text": state.get("draft", "")},
                    "discardResult": True,
                },
                {"method": "editor.save"},
            ],
            "next": "saved",
        }
    elif params["id"] == "saved":
        state["status"] = "保存完成"
    await ctx.storage.set("state", state)


def register(host):
    host.register_command("ui.render", render)
    host.register_command("ui.action", action)
