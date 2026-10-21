"""Public SDK only; never reads application models or development internals."""

CSS = ".demo { padding:16px; border:1px solid var(--accent-7); border-radius:12px; }"


def node(kind, children=None, **props):
    return {"type": kind, "props": props, "children": children}


async def render(ctx, params):
    count = await ctx.storage.get("count", 0)
    content = node(
        "Box",
        [
            node("Heading", "原生 SDK 开发示例", size="4"),
            node("Text", f"计数：{count}", id="demo-count"),
            node("Button", "增加计数", onPress="increment"),
            node("Button", "触发权限错误", onPress="permission"),
            node("Button", "触发 CSS 诊断", onPress="css-warning"),
            node("Button", "验证密钥脱敏", onPress="secret"),
        ],
        className="demo",
    )
    if params["viewId"] == "floating":
        content = node(
            "FloatingPanel",
            content,
            width=260,
            dragLabel="移动开发示例",
            position=await ctx.storage.get("position"),
            onPositionChange="position",
        )
    css = CSS
    if await ctx.storage.get("css-warning", False):
        css += '@import url("https://example.com/ignored.css");'
    return {"tree": content, "css": css}
