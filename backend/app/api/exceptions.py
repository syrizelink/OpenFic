# -*- coding: utf-8 -*-
"""
全局异常处理器。

将领域层异常统一映射为 HTTP 响应。1
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.errors import (
    NotFoundError,
    OpenFicError,
    ProjectAlreadyBoundError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器。

    Args:
        app: FastAPI 应用实例。
    """

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        """处理资源不存在错误。"""
        logger.opt(exception=True).debug(
            "request failed: {} {}", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ProjectAlreadyBoundError)
    async def project_already_bound_error_handler(
        request: Request, exc: ProjectAlreadyBoundError
    ) -> JSONResponse:
        """处理项目已绑定世界书错误。"""
        logger.opt(exception=True).debug(
            "request failed: {} {}", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request, exc: ValueError
    ) -> JSONResponse:
        """处理值错误（通常是无效参数）。"""
        logger.opt(exception=True).debug(
            "request failed: {} {}", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(OpenFicError)
    async def openfic_error_handler(
        request: Request, exc: OpenFicError
    ) -> JSONResponse:
        """处理其他 OpenFic 领域错误。"""
        logger.opt(exception=True).debug(
            "request failed: {} {}", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """处理显式抛出的 HTTPException，记录 DEBUG 堆栈。"""
        logger.opt(exception=True).debug(
            "request failed: {} {}", request.method, request.url.path
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
