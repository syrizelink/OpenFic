"""Independent generic SDK probe, unrelated to the whale port."""


async def render(ctx, params):
    value = await ctx.storage.get("value", "")
    return {
        "tree": {
            "type": "FloatingPanel",
            "props": {
                "width": 220,
                "position": {"x": 12, "y": 90},
                "dragLabel": "移动独立面板",
            },
            "children": {
                "type": "Card",
                "children": [
                    {"type": "Text", "children": "独立浮层探针"},
                    {
                        "type": "Input",
                        "props": {
                            "label": "探针输入",
                            "value": value,
                            "onInput": "edit",
                        },
                    },
                    {"type": "Text", "props": {"id": "echo"}, "children": value},
                    {
                        "type": "Image",
                        "props": {"asset": "assets/unsafe.svg", "alt": "拒绝 SVG"},
                    },
                ],
            },
        }
    }


async def action(ctx, params):
    await ctx.storage.set("value", params["value"])


def register(host):
    host.register_command("ui.render", render)
    host.register_command("ui.action", action)
