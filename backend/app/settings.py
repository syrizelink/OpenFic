"""
Application settings using pydantic-settings.
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet
from loguru import logger
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
BACKEND_DATA_DIR = Path(os.getenv("OPENFIC_DATA_DIR", str(BACKEND_DIR / "data")))
ENV_FILE_PATH = BACKEND_DATA_DIR / ".env"
ENCRYPTION_KEY_FILE_PATH = BACKEND_DATA_DIR / ".key"


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

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Storage
    covers_dir: Path = BACKEND_DATA_DIR / "covers"
    character_images_dir: Path = BACKEND_DATA_DIR / "character-images"
    static_dir: Path = BACKEND_DATA_DIR

    # Background runtime
    background_enabled: bool = True
    background_worker_enabled: bool = True
    background_worker_id: str | None = None
    background_worker_concurrency: int = 1
    background_job_scan_interval_seconds: float = 5.0
    background_running_stale_seconds: int = 600
    background_zmq_job_endpoint: str = "inproc://background-jobs"
    background_zmq_event_endpoint: str = "inproc://background-events"

    # Security - Encryption key for sensitive data (API keys, etc.)
    encryption_key: str = _ensure_encryption_key()

    @property
    def database_url(self) -> str:
        data_dir = BACKEND_DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{data_dir}/openfic.db"

    @property
    def checkpoint_db_path(self) -> Path:
        data_dir = BACKEND_DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "checkpoints.db"


settings = Settings()
