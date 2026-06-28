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
# .env 必须落到可写的数据目录（打包后为 userData），避免相对 CWD 写入不可写位置
ENV_FILE_PATH = BACKEND_DATA_DIR / ".env"
# 历史位置（开发态 backend/.env），仅用于读取已存在的密钥，防止现有加密数据失效
_LEGACY_ENV_FILE_PATH = BACKEND_DIR / ".env"


def _read_encryption_key_from(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ENCRYPTION_KEY=") and not line.startswith("#"):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        return key
    except OSError:
        return None
    return None


def _ensure_encryption_key() -> str:
    """
    确保加密密钥存在。

    优先级：环境变量 > 数据目录 .env > 历史位置 .env > 新生成并写入数据目录。
    所有路径均为绝对路径，不依赖当前工作目录。

    Returns:
        加密密钥字符串。
    """
    env_key = os.getenv("ENCRYPTION_KEY")
    if env_key:
        return env_key

    key = _read_encryption_key_from(ENV_FILE_PATH)
    if key:
        return key

    key = _read_encryption_key_from(_LEGACY_ENV_FILE_PATH)
    if key:
        return key

    new_key = Fernet.generate_key().decode()
    logger.info("生成新的加密密钥并保存到数据目录")
    ENV_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(f'ENCRYPTION_KEY="{new_key}"\n')

    return new_key


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "OpenFic"
    app_version: str = "0.0.0"
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
    # 如果未在环境变量或 .env 文件中设置，将自动生成并保存
    encryption_key: str = _ensure_encryption_key()

    @property
    def database_url(self) -> str:
        """
        获取数据库 URL，自动创建 data 目录。

        Returns:
            SQLite 数据库连接 URL。
        """
        data_dir = BACKEND_DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{data_dir}/openfic.db"

    @property
    def checkpoint_db_path(self) -> Path:
        """获取统一的 runtime checkpoint 数据库路径。"""
        data_dir = BACKEND_DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "checkpoints.db"


settings = Settings()
