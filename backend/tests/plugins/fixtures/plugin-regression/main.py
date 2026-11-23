async def observe(context, event, next):
    return await next(event)


async def open_panel(context, params):
    return {
        "effects": [
            {
                "method": "ui.openOverlay",
                "params": {
                    "viewId": "editor-panel",
                    "anchor": params["context"]["anchor"],
                },
            }
        ]
    }


def register(host):
    host.register_command("open", open_panel)
    for event in [
        "session.start",
        "session.end",
        "turn.start",
        "turn.complete",
        "prompt.submit",
        "context.build",
        "tool.call",
        "tool.result",
        "data.changed",
        "agent.spawn",
    ]:
        host.register_hook(event, observe)
