"""Notify plugins of successful application writes without inspecting bodies."""

from app.plugins.runtime import dispatch


class PluginEventsMiddleware:
    def __init__(self, app, *, api_prefix="/api/v1"):
        self.app, self.prefix = app, api_prefix

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if (
            scope["type"] != "http"
            or scope.get("method") not in {"POST", "PUT", "PATCH", "DELETE"}
            or not path.startswith(self.prefix + "/")
            or path.startswith(self.prefix + "/plugins")
            or path.startswith(self.prefix + "/auth")
        ):
            return await self.app(scope, receive, send)
        status = 500

        async def record(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        await self.app(scope, receive, record)
        if status < 400:
            from app.plugins.host import active_host

            host = active_host()
            if host:
                event = {
                    "path": path.removeprefix(self.prefix),
                    "method": scope["method"],
                }
                host.emit("data.changed", event)
                if any(
                    p.registration and p.registration.hooks.get("data.changed")
                    for p in host.plugins.values()
                ):
                    from app.storage.database import create_session

                    try:
                        async with await create_session() as session:
                            await dispatch("data.changed", event, session, host=host)
                            await session.commit()
                    except Exception as error:
                        from loguru import logger

                        logger.warning("Plugin data.changed handler failed: {}", error)
