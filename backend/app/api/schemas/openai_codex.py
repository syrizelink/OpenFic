from typing import Literal

from pydantic import BaseModel, Field


class OpenAICodexAuthStartRequest(BaseModel):
    provider_id: str | None = Field(default=None)
    registration_id: str | None = Field(default=None)
    new_registration: bool = False


class OpenAICodexAuthStartResponse(BaseModel):
    authorization_url: str
    authorization_id: str
    provider_id: str | None = None


class OpenAICodexAuthStatusResponse(BaseModel):
    status: Literal["pending", "success", "error", "expired"]
    provider_id: str | None = None
    registration_id: str | None = None


class OpenAICodexRegistrationResponse(BaseModel):
    client_id: str
    email: str | None
    provider_id: str | None
    verified: bool


class OpenAICodexManualCallbackRequest(BaseModel):
    authorization_id: str = Field(min_length=1, max_length=128)
    callback_url: str = Field(min_length=1, max_length=16384)
