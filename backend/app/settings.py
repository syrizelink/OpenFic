"""
Application settings using pydantic-settings.
"""

import os
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from loguru import logger
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


BACKEND_DIR = Path(__file__).resolve().parents[1]
BACKEND_DATA_DIR = Path(os.getenv("OPENFIC_DATA_DIR", str(BACKEND_DIR / "data")))
ENV_FILE_PATH = BACKEND_DATA_DIR / ".env"
ENCRYPTION_KEY_FILE_PATH = BACKEND_DATA_DIR / ".key"
_DATABASE_URL_SCHEMES = {
    "sqlite": "sqlite+aiosqlite",
    "postgresql": "postgresql+psycopg",
}


def _read_encryption_key_from_file(path: Path) -> str | None:
    if not path.exists():
        return None

    try:
        key = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    if not key:
        return None

    logger.info("Loaded ENCRYPTION_KEY from .key file")
    return key


def to_sync_database_url(database_url: str) -> str:
    """将应用数据库 URL 转换为同步 SQLAlchemy URL。"""
    parsed_url = make_url(database_url)
    backend = parsed_url.get_backend_name()
    if backend == "sqlite":
        parsed_url = parsed_url.set(drivername="sqlite")
    elif backend == "postgresql" and parsed_url.get_driver_name() != "psycopg":
        parsed_url = parsed_url.set(drivername="postgresql+psycopg")
    return parsed_url.render_as_string(hide_password=False)


def _ensure_encryption_key() -> str:
    key = _read_encryption_key_from_file(ENCRYPTION_KEY_FILE_PATH)
    if key:
        return key

    logger.info("Generating new ENCRYPTION_KEY")
    ENCRYPTION_KEY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENCRYPTION_KEY_FILE_PATH.write_text(Fernet.generate_key().decode(), encoding="utf-8")

    key = _read_encryption_key_from_file(ENCRYPTION_KEY_FILE_PATH)
    if key:
        return key

    raise RuntimeError("Failed to load ENCRYPTION_KEY from .key file")


def _read_package_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("openfic")
    except (PackageNotFoundError, Exception):
        return "0.0.0"


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "OpenFic"
    app_version: str = _read_package_version()
    debug: bool = False

    @field_validator("debug", mode="before")
    @classmethod
    def _coerce_debug(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on"}
        return bool(v)

    # API
    api_v1_prefix: str = "/api/v1"

    # Optional application password gate. Empty or unset means disabled.
    auth_password: str | None = Field(default=None, validation_alias="OPENFIC_AUTH_PASSWORD")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Storage
    database_backend: Literal["sqlite", "postgresql"] = Field(
        default="sqlite",
        validation_alias="OPENFIC_DATABASE_BACKEND",
    )
    database_url_override: str | None = Field(
        default=None,
        validation_alias="OPENFIC_DATABASE_URL",
    )
    checkpoint_database_url: str | None = Field(
        default=None,
        validation_alias="OPENFIC_CHECKPOINT_DATABASE_URL",
    )
    covers_dir: Path = BACKEND_DATA_DIR / "covers"
    character_images_dir: Path = BACKEND_DATA_DIR / "character-images"
    agent_attachments_dir: Path = BACKEND_DATA_DIR / "agent-attachments"
    chapter_exports_dir: Path = BACKEND_DATA_DIR / "chapter-exports"
    static_dir: Path = BACKEND_DATA_DIR

    @field_validator("database_backend", mode="before")
    @classmethod
    def _normalize_database_backend(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("database_url_override", "checkpoint_database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: object) -> object:
        if isinstance(v, str):
            value = v.strip()
            return value or None
        return v

    @model_validator(mode="after")
    def _validate_database_configuration(self) -> Self:
        if self.database_backend == "postgresql" and not self.database_url_override:
            raise ValueError(
                "OPENFIC_DATABASE_URL is required when "
                "OPENFIC_DATABASE_BACKEND is postgresql"
            )
        if self.database_url_override:
            expected_scheme = _DATABASE_URL_SCHEMES[self.database_backend]
            actual_scheme = urlsplit(self.database_url_override).scheme
            if actual_scheme != expected_scheme:
                raise ValueError(
                    "OPENFIC_DATABASE_URL must use "
                    f"{expected_scheme} when OPENFIC_DATABASE_BACKEND is "
                    f"{self.database_backend}"
                )
        if self.database_backend == "sqlite" and self.checkpoint_database_url:
            raise ValueError(
                "OPENFIC_CHECKPOINT_DATABASE_URL is only supported when "
                "OPENFIC_DATABASE_BACKEND is postgresql"
            )
        if self.checkpoint_database_url:
            actual_scheme = urlsplit(self.checkpoint_database_url).scheme
            if actual_scheme not in {"postgresql", "postgres"}:
                raise ValueError(
                    "OPENFIC_CHECKPOINT_DATABASE_URL must use "
                    "postgresql:// or postgres://"
                )
        return self

    # Background runtime
    background_enabled: bool = True
    background_worker_enabled: bool = True
    background_worker_id: str | None = None
    background_worker_concurrency: int = 1
    background_job_scan_interval_seconds: float = 5.0
    background_running_stale_seconds: int = 600
    background_zmq_job_endpoint: str = "inproc://background-jobs"
    background_zmq_event_endpoint: str = "inproc://background-events"

    # LLM invocation timeouts & retries
    llm_connect_timeout: float = 10.0
    llm_chunk_timeout: float = 120.0
    llm_request_timeout: float = 600.0
    llm_retry_max_attempts: int = 5
    llm_retry_base_interval: float = 2.0
    llm_retry_max_interval: float = 30.0
    llm_empty_response_retries: int = 2

    # Security - Encryption key for sensitive data (API keys, etc.)
    encryption_key: str = _ensure_encryption_key()

    # Telemetry - PostHog error reporting (project API key, safe to expose)
    posthog_api_key: str = "phc_kHbik4h8n5KHfZxyTbddA2p6y8zxRNGpsDBNycizyK68"
    posthog_host: str = "https://us.i.posthog.com"

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override

        data_dir = BACKEND_DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{data_dir}/openfic.db"

    @property
    def database_sync_url(self) -> str:
        """获取供同步数据库工具使用的 URL。"""
        return to_sync_database_url(self.database_url)

    @property
    def checkpoint_db_path(self) -> Path:
        data_dir = BACKEND_DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "checkpoints.db"


settings = Settings()
