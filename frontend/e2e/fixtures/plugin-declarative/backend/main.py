"""Installable mixed-renderer fixture, also used in transport contract tests."""


def component(kind, children=None, **props):
    return {"type": kind, "props": props, "children": children}


async def render(context, params):
    state = await context.storage.get("state", {})
    children = [
        component("Text", "<img src=x onerror=alert(1)>"),
        component("Text", f"Count: {state.get('count', 0)}"),
        component("Button", label="Increment", onPress="increment"),
        component(
            "Input",
            key="name",
            label="Name",
            value=state.get("name", ""),
            onInput="name",
            onSubmit="submit",
        ),
        component("Text", f"Name: {state.get('name', '')}"),
        component("Text", f"Submitted: {state.get('submitted', '')}"),
        component(
            "Select",
            label="Mode",
            value=state.get("mode", "one"),
            options=[
                {"value": "one", "label": "First"},
                {"value": "two", "label": "Second"},
            ],
            onSelect="mode",
        ),
        component("Text", f"Mode: {state.get('mode', 'one')}"),
        component(
            "Checkbox",
            label="Enabled",
            checked=state.get("enabled", False),
            onChange="enabled",
        ),
        component(
            "Switch",
            label="Automatic",
            checked=state.get("automatic", False),
            onChange="automatic",
        ),
        component("Link", "Unsafe URL", href="javascript:alert(1)"),
        component("Code", "const safe = true;"),
        component("Markdown", "<script>alert(1)</script>"),
        component("Badge", "Native badge"),
        component("Progress", label="Completion", value=40),
        component("Separator"),
    ]
    return {"tree": component("Box", children, gap=2)}


async def action(context, params):
    state = await context.storage.get("state", {})
    identity = params["id"]
    if identity == "increment":
        state["count"] = state.get("count", 0) + 1
    elif identity in {"name", "mode", "enabled", "automatic"}:
        state[identity] = params["value"]
    elif identity == "submit":
        state["submitted"] = params["value"]
    else:
        raise ValueError("Unknown action")
    await context.storage.set("state", state)


def register(host):
    host.register_command("ui.render", render)
    host.register_command("ui.action", action)
