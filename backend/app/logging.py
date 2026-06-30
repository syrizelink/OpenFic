from __future__ import annotations

import logging
from typing import Any

from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if _should_skip_log_record(record):
            return

        level = _resolve_loguru_level(record)

        def _patch_record(log_record: Any) -> None:
            log_record["name"] = record.name
            log_record["function"] = record.funcName
            log_record["line"] = record.lineno

        patched_logger = logger.patch(_patch_record)
        patched_logger.opt(exception=record.exc_info).log(level, record.getMessage())


def _resolve_loguru_level(record: logging.LogRecord) -> str | int:
    if record.name == "alembic.runtime.migration" and record.getMessage().startswith("Running upgrade"):
        return "DEBUG"

    try:
        return logger.level(record.levelname).name
    except ValueError:
        return record.levelno


def _should_skip_log_record(record: logging.LogRecord) -> bool:
    return record.name == "uvicorn.error" and record.getMessage().startswith("Uvicorn running on ")


def configure_standard_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers = [InterceptHandler()]
    root_logger.setLevel(level)

    for logger_name in (
        "alembic",
        "alembic.runtime.migration",
        "alembic.runtime.plugins",
        "sqlalchemy",
        "sqlalchemy.engine",
        "uvicorn",
        "uvicorn.error",
    ):
        named_logger = logging.getLogger(logger_name)
        named_logger.handlers.clear()
        named_logger.propagate = True
        named_logger.disabled = False

    logging.getLogger("alembic").setLevel(logging.WARNING)
    logging.getLogger("alembic.runtime.migration").setLevel(logging.DEBUG)
    logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)

    logging.captureWarnings(True)
