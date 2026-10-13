"""Control the tunnel belonging to this backend instance."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from app.tunnels import TunnelManager, TunnelStart


class TunnelRoute(APIRoute):
    """Never echo token-bearing request bodies in validation responses."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def sanitized_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                raise HTTPException(
                    422,
                    [
                        {key: error[key] for key in ("loc", "msg", "type")}
                        for error in exc.errors()
                    ],
                ) from None

        return sanitized_handler


router = APIRouter(prefix="/tunnels", tags=["tunnels"], route_class=TunnelRoute)


def manager(request: Request) -> TunnelManager:
    return request.app.state.tunnel_manager


@router.get("")
async def get_tunnel(request: Request) -> dict:
    return {
        **manager(request).snapshot(),
        "auth_enabled": request.app.state.auth_service.enabled,
        "frontend_available": request.app.state.tunnel_frontend_available,
    }


@router.post("/start")
async def start_tunnel(payload: TunnelStart, request: Request) -> dict:
    if not request.app.state.auth_service.enabled:
        raise HTTPException(
            409, "Configure OPENFIC_AUTH_PASSWORD and restart OpenFic first"
        )
    if not request.app.state.tunnel_frontend_available:
        raise HTTPException(
            409, "Build or install the OpenFic frontend before starting a tunnel"
        )
    server = request.scope.get("server")
    if not server or not server[1]:
        raise HTTPException(409, "Cannot determine the OpenFic server port")
    try:
        return await manager(request).start(payload, server[1])
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/stop")
async def stop_tunnel(request: Request) -> dict:
    return await manager(request).stop()
