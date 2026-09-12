# -*- coding: utf-8 -*-
"""
Penangan exception global.

Memetakan exception lapisan domain secara seragam menjadi respons HTTP.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.errors import (
    ConflictError,
    NotFoundError,
    OpenFicError,
    ProjectAlreadyBoundError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Mendaftarkan penangan exception global.

    Args:
        app: Instance aplikasi FastAPI.
    """

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        """Menangani error resource tidak ditemukan."""
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
        """Menangani error proyek sudah terikat buku dunia."""
        logger.opt(exception=True).debug(
            "request failed: {} {}", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(
        request: Request, exc: ConflictError
    ) -> JSONResponse:
        """Menangani error konflik resource."""
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
        """Menangani ValueError (biasanya parameter tidak valid)."""
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
        """Menangani error domain OpenFic lainnya."""
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
        """Menangani HTTPException yang dilempar eksplisit, mencatat stack trace DEBUG."""
        logger.opt(exception=True).debug(
            "request failed: {} {}", request.method, request.url.path
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Menangani exception yang tidak tertangkap: mengembalikan 500 generik, lalu melaporkan telemetri error."""
        logger.bind(
            request_method=request.method,
            request_path=request.url.path,
        ).opt(exception=exc).error("unhandled exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal Server Error"},
        )
