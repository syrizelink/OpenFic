"""OAuth client metadata retained independently from provider credentials."""

from sqlmodel import Field, SQLModel


class ModelProviderOAuthRegistration(SQLModel, table=True):
    __tablename__ = "model_provider_oauth_registrations"

    provider_type: str = Field(primary_key=True, max_length=255)
    issuer: str = Field(primary_key=True, max_length=255)
    client_id: str = Field(primary_key=True, max_length=255)
    subject: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    provider_id: str | None = Field(default=None, index=True, max_length=255)
