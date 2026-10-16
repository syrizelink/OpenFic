"""Control the tunnel belonging to this backend instance."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database import get_session
from app.tunnels import (
    TunnelConfigUpdate,
    TunnelManager,
    TunnelStart,
    TunnelStartRequest,
)
from app.tunnels_config import (
    TunnelConfig,
    load_tunnel_config,
    public_tunnel_config,
    save_tunnel_config,
    update_tunnel_config,
)


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
async def get_tunnel(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    config = await load_tunnel_config(session)
    return {
        **manager(request).snapshot(),
        "auth_enabled": request.app.state.auth_service.enabled,
        "frontend_available": request.app.state.tunnel_frontend_available,
        "config": public_tunnel_config(config),
    }


@router.put("/config")
async def update_config(
    payload: TunnelConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    config = await update_tunnel_config(session, payload)
    await session.commit()
    return public_tunnel_config(config)


@router.post("/start")
async def start_tunnel(
    payload: TunnelStartRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
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

    persisted_config = await load_tunnel_config(session)
    provider = payload.provider or persisted_config.provider
    mode = payload.mode or persisted_config.mode
    hostname = payload.hostname if payload.hostname is not None else persisted_config.hostname
    token = (
        payload.token.get_secret_value().strip()
        if payload.token is not None and payload.token.get_secret_value().strip()
        else persisted_config.token
    )
    try:
        start_payload = TunnelStart(
            provider=provider,
            mode=mode,
            token=SecretStr(token) if token else None,
            hostname=hostname,
        )
    except ValidationError as exc:
        raise HTTPException(
            422,
            [
                {key: error[key] for key in ("loc", "msg", "type")}
                for error in exc.errors()
            ],
        ) from None

    await save_tunnel_config(
        session,
        TunnelConfig(
            provider=start_payload.provider,
            mode=start_payload.mode,
            hostname=start_payload.hostname,
            token=token,
        ),
    )
    await session.commit()
    try:
        return await manager(request).start(start_payload, server[1])
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/stop")
async def stop_tunnel(request: Request) -> dict:
    return await manager(request).stop()
