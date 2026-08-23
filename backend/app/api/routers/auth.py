"""Authentication endpoints for the optional application password gate."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.settings import get_settings
from app.auth import AUTH_COOKIE_MAX_AGE, AUTH_COOKIE_NAME, AuthService
from app.storage.database import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatusResponse(BaseModel):
    enabled: bool
    authenticated: bool


class AuthLoginRequest(BaseModel):
    password: str
    trust_device: bool = False


class PublicPreferencesResponse(BaseModel):
    language: str
    theme: str
    font_family: str
    code_font_family: str
    base_font_size: int
    editor_font_size: int


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthStatusResponse:
    return AuthStatusResponse(
        enabled=auth_service.enabled,
        authenticated=auth_service.verify_cookie_value(request.cookies.get(AUTH_COOKIE_NAME)),
    )


@router.get("/preferences", response_model=PublicPreferencesResponse)
async def public_preferences(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PublicPreferencesResponse:
    settings = await get_settings(session)
    return PublicPreferencesResponse(
        language=settings.language,
        theme=settings.theme,
        font_family=settings.font_family,
        code_font_family=settings.code_font_family,
        base_font_size=settings.base_font_size,
        editor_font_size=settings.editor_font_size,
    )


@router.post("/login", response_model=AuthStatusResponse)
async def login(
    payload: AuthLoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthStatusResponse:
    if not auth_service.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not auth_service.verify_password(payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=auth_service.create_cookie_value(),
        max_age=AUTH_COOKIE_MAX_AGE if payload.trust_device else None,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return AuthStatusResponse(enabled=True, authenticated=True)
