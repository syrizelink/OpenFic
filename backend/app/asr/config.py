"""Validated, encrypted ASR settings, independent of chat model credentials."""

from pathlib import Path
from typing import Literal, get_args
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.settings import settings
from app.storage.repos import setting_repo

SETTING_KEY = "asr_config"
Provider = Literal[
    "sensevoice", "whisper", "openai", "groq", "mistral", "deepgram", "azure"
]
DEFAULTS = {
    "openai": ("https://api.openai.com/v1", "whisper-1"),
    "groq": ("https://api.groq.com/openai/v1", "whisper-large-v3-turbo"),
    "mistral": ("https://api.mistral.ai/v1", "voxtral-mini-latest"),
    "deepgram": ("https://api.deepgram.com/v1", "nova-3"),
    "azure": ("https://eastus.api.cognitive.microsoft.com", ""),
}


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str = Field(default="", max_length=2048)
    model: str = Field(default="", max_length=256)
    model_path: str = Field(default="", max_length=4096)
    tokens_path: str = Field(default="", max_length=4096)
    vad_path: str = Field(default="", max_length=4096)
    api_key_encrypted: str = ""

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if value:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "Use an HTTP(S) base URL without credentials, query or fragment"
                )
        return value

    @field_validator("model_path", "tokens_path", "vad_path")
    @classmethod
    def absolute_path(cls, value: str) -> str:
        value = value.strip()
        if value and not Path(value).is_absolute():
            raise ValueError("Model paths must be absolute")
        return value


class ASRConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    provider: Provider = "sensevoice"
    language: str = Field(
        default="auto", pattern=r"^(auto|[a-z]{2,3}(-[A-Za-z]{2,4})?)$"
    )
    providers: dict[Provider, ProviderConfig] = Field(default_factory=dict)


class ASRUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    provider: Provider
    language: str = Field(
        default="auto", pattern=r"^(auto|[a-z]{2,3}(-[A-Za-z]{2,4})?)$"
    )
    config: ProviderConfig = Field(default_factory=ProviderConfig)
    # Omission/null preserves the selected provider's key; an empty string clears it.
    api_key: str | None = Field(default=None, max_length=8192)


async def load_config(session: AsyncSession) -> ASRConfig:
    row = await setting_repo.get_by_key(session, SETTING_KEY)
    return ASRConfig.model_validate_json(row.value) if row else ASRConfig()


def public_config(config: ASRConfig) -> dict:
    result = config.model_dump()
    for provider in get_args(Provider):
        value = config.providers.get(provider, ProviderConfig())
        result["providers"][provider] = {
            **value.model_dump(exclude={"api_key_encrypted"}),
            "has_api_key": bool(value.api_key_encrypted),
        }
    return result


def decrypt_key(config: ProviderConfig) -> str:
    return (
        EncryptionService(settings.encryption_key).decrypt(config.api_key_encrypted)
        if config.api_key_encrypted
        else ""
    )
