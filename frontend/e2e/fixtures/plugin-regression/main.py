async def observe(context, event, next):
    return await next(event)


def register(host):
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
