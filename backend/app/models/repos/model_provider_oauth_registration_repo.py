"""Persist issued client IDs without retaining access, refresh or ID tokens."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.models.entities.model_provider_oauth_registration import ModelProviderOAuthRegistration


async def get_by_client_id(
    session: AsyncSession, *, provider_type: str, issuer: str, client_id: str,
) -> ModelProviderOAuthRegistration | None:
    return await session.get(ModelProviderOAuthRegistration, {
        "provider_type": provider_type, "issuer": issuer, "client_id": client_id,
    })


async def get_for_provider(
    session: AsyncSession, *, provider_type: str, issuer: str, provider_id: str,
) -> ModelProviderOAuthRegistration | None:
    result = await session.execute(select(ModelProviderOAuthRegistration).where(
        col(ModelProviderOAuthRegistration.provider_type) == provider_type,
        col(ModelProviderOAuthRegistration.issuer) == issuer,
        col(ModelProviderOAuthRegistration.provider_id) == provider_id,
    ))
    return result.scalars().first()


async def get_all(
    session: AsyncSession, *, provider_type: str, issuer: str,
) -> list[ModelProviderOAuthRegistration]:
    result = await session.execute(select(ModelProviderOAuthRegistration).where(
        col(ModelProviderOAuthRegistration.provider_type) == provider_type,
        col(ModelProviderOAuthRegistration.issuer) == issuer,
    ).order_by(ModelProviderOAuthRegistration.client_id))
    return list(result.scalars().all())


async def save_issued(
    session: AsyncSession, *, provider_type: str, issuer: str, client_id: str,
) -> ModelProviderOAuthRegistration:
    registration = await get_by_client_id(session, provider_type=provider_type, issuer=issuer, client_id=client_id)
    if registration is None:
        registration = ModelProviderOAuthRegistration(provider_type=provider_type, issuer=issuer, client_id=client_id)
        session.add(registration)
        await session.flush()
    return registration


async def save_verified(
    session: AsyncSession, *, provider_type: str, issuer: str, client_id: str,
    subject: str, email: str | None, provider_id: str | None,
) -> ModelProviderOAuthRegistration:
    registration = await save_issued(session, provider_type=provider_type, issuer=issuer, client_id=client_id)
    if registration.subject is not None and registration.subject != subject:
        raise ValueError("OAuth registration identity does not match the saved account")
    registration.subject = subject
    registration.email = email
    registration.provider_id = provider_id
    session.add(registration)
    return registration
