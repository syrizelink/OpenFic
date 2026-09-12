# -*- coding: utf-8 -*-
"""
ModelProvider Router - API penyedia layanan model.
"""

from typing import Annotated
import json

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    status,
)
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.model_provider import (
    AvailableModel,
    CatalogMatchResponse,
    CustomHeaderEntry,
    ModelProviderResponse,
    ModelProviderValidateRequest,
    ModelProviderValidateResponse,
)
from app.api.agent_settings_lock import require_agent_settings_unlocked
from app.models.catalog import ModelProviderCatalogService
from app.core.encryption import EncryptionService
from app.core.errors import NotFoundError
from app.settings import settings
from app.storage.database import get_session
from app.models.services import ModelProviderService

router = APIRouter(prefix="/model-providers", tags=["model-providers"])


def get_encryption_service() -> EncryptionService:
    """Mengambil instance layanan enkripsi."""
    return EncryptionService(settings.encryption_key)


def get_catalog_service() -> ModelProviderCatalogService:
    """Mengambil instance layanan catalog."""
    return ModelProviderCatalogService()


def get_provider_service(
    encryption_service: Annotated[EncryptionService, Depends(get_encryption_service)],
    catalog_service: Annotated[
        ModelProviderCatalogService, Depends(get_catalog_service)
    ],
) -> ModelProviderService:
    """Mengambil instance layanan penyedia."""
    return ModelProviderService(encryption_service, catalog_service)


def _parse_custom_headers(raw_headers: str | None) -> list[dict[str, str]] | None:
    """Mengurai JSON header permintaan kustom dari formulir multipart."""
    if raw_headers is None:
        return None
    if not raw_headers.strip():
        return []

    try:
        payload = json.loads(raw_headers)
        if not isinstance(payload, list):
            raise ValueError
        return [
            CustomHeaderEntry.model_validate(item).model_dump(mode="json")
            for item in payload
        ]
    except (ValueError, TypeError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format header permintaan kustom tidak valid",
        ) from exc


async def _build_provider_response(
    provider,
    service: ModelProviderService,
) -> ModelProviderResponse:
    catalog_match = await service.get_catalog_match(provider)
    supported_task_types = await service.get_supported_task_types(
        provider, catalog_match=catalog_match
    )
    icon_path = await service.get_effective_icon_path(
        provider, catalog_match=catalog_match
    )

    return ModelProviderResponse(
        id=provider.id,
        name=provider.name,
        url=provider.url,
        provider_type=provider.provider_type,
        custom_header_names=service.get_custom_header_names(provider),
        supported_task_types=supported_task_types,
        icon_path=icon_path,
        is_builtin=provider.is_builtin,
        catalog_match=(
            CatalogMatchResponse.model_validate(catalog_match.model_dump())
            if catalog_match is not None
            else None
        ),
        created_at=provider.created_at.isoformat(),
        updated_at=provider.updated_at.isoformat(),
    )


@router.get(
    "",
    response_model=list[ModelProviderResponse],
    summary="Mengambil semua penyedia",
)
async def get_providers(
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelProviderService, Depends(get_provider_service)],
) -> list[ModelProviderResponse]:
    """
    Mengambil semua penyedia layanan model.

    Args:
        session: Session basis data.
        service: Layanan penyedia.

    Returns:
        Daftar penyedia.
    """
    providers = await service.get_all_providers(session)
    return [await _build_provider_response(provider, service) for provider in providers]


@router.get(
    "/{provider_id}",
    response_model=ModelProviderResponse,
    summary="Mengambil penyedia",
)
async def get_provider(
    provider_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelProviderService, Depends(get_provider_service)],
) -> ModelProviderResponse:
    """
    Mengambil penyedia berdasarkan ID.

    Args:
        provider_id: ID penyedia.
        session: Session basis data.
        service: Layanan penyedia.

    Returns:
        Informasi penyedia.

    Raises:
        HTTPException: Bila penyedia tidak ditemukan.
    """
    try:
        provider = await service.get_provider_by_id(session, provider_id)
        return await _build_provider_response(provider, service)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "",
    response_model=ModelProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Membuat penyedia",
)
async def create_provider(
    url: Annotated[str, Form()],
    provider_type: Annotated[str, Form()],
    name: Annotated[str, Form()] = "",
    api_key: Annotated[str | None, Form()] = None,
    custom_headers: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),
    service: ModelProviderService = Depends(get_provider_service),
) -> ModelProviderResponse:
    """
    Membuat penyedia layanan model.

    Args:
        name: Nama/catatan penyedia.
        url: URL layanan.
        api_key: API Key.
        provider_type: Tipe penyedia.
        session: Session basis data.
        service: Layanan penyedia.

    Returns:
        Informasi penyedia yang dibuat.
    """
    await require_agent_settings_unlocked(session)
    logger.info(f"Membuat penyedia: {provider_type}")

    try:
        provider = await service.create_provider(
            session=session,
            name=name,
            url=url,
            api_key=api_key or "",
            provider_type=provider_type,
            custom_headers=_parse_custom_headers(custom_headers),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return await _build_provider_response(provider, service)


@router.put(
    "/{provider_id}",
    response_model=ModelProviderResponse,
    summary="Memperbarui penyedia",
)
async def update_provider(
    provider_id: str,
    name: Annotated[str | None, Form()] = None,
    url: Annotated[str | None, Form()] = None,
    api_key: Annotated[str | None, Form()] = None,
    provider_type: Annotated[str | None, Form()] = None,
    custom_headers: Annotated[str | None, Form()] = None,
    session: AsyncSession = Depends(get_session),
    service: ModelProviderService = Depends(get_provider_service),
) -> ModelProviderResponse:
    """
    Memperbarui informasi penyedia.

    Args:
        provider_id: ID penyedia.
        name: Nama/catatan penyedia.
        url: URL layanan.
        api_key: API Key.
        provider_type: Tipe penyedia.
        session: Session basis data.
        service: Layanan penyedia.

    Returns:
        Informasi penyedia setelah diperbarui.

    Raises:
        HTTPException: Bila penyedia tidak ditemukan.
    """
    await require_agent_settings_unlocked(session)
    logger.info(f"Memperbarui penyedia: {provider_id}")

    try:
        provider = await service.update_provider(
            session=session,
            provider_id=provider_id,
            name=name,
            url=url,
            api_key=api_key,
            provider_type=provider_type,
            custom_headers=_parse_custom_headers(custom_headers),
        )

        return await _build_provider_response(provider, service)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Menghapus penyedia",
)
async def delete_provider(
    provider_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelProviderService, Depends(get_provider_service)],
) -> None:
    """
    Menghapus penyedia.

    Args:
        provider_id: ID penyedia.
        session: Session basis data.
        service: Layanan penyedia.

    Raises:
        HTTPException: Bila penyedia tidak ditemukan.
    """
    await require_agent_settings_unlocked(session)
    logger.info(f"Menghapus penyedia: {provider_id}")

    try:
        await service.delete_provider(session, provider_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/validate",
    response_model=ModelProviderValidateResponse,
    summary="Memvalidasi koneksi penyedia",
)
async def validate_provider(
    request: ModelProviderValidateRequest,
    service: Annotated[ModelProviderService, Depends(get_provider_service)],
) -> ModelProviderValidateResponse:
    """
    Memvalidasi koneksi penyedia dan mengambil daftar model yang tersedia.

    Args:
        request: Permintaan validasi.
        service: Layanan penyedia.

    Returns:
        Hasil validasi dan daftar model yang tersedia.
    """
    logger.info(f"Memvalidasi koneksi penyedia: {request.provider_type}")

    try:
        models = await service.validate_and_get_models(
            provider_type=request.provider_type,
            url=request.url,
            api_key=request.api_key,
            custom_headers=[item.model_dump(mode="json") for item in request.custom_headers],
        )
        return ModelProviderValidateResponse(
            success=True,
            message="Validasi koneksi berhasil"
            if models
            else "Validasi koneksi berhasil, tetapi penyedia ini mungkin tidak mendukung daftar model API",
            models=[
                AvailableModel(
                    id=m["id"],
                    name=m["name"],
                )
                for m in models
            ],
        )
    except Exception as e:
        logger.error(f"Gagal memvalidasi koneksi penyedia: {e}")
        return ModelProviderValidateResponse(
            success=False,
            message=f"Validasi koneksi gagal: {str(e)}",
            models=[],
        )


@router.get(
    "/{provider_id}/models",
    response_model=ModelProviderValidateResponse,
    summary="Mengambil daftar model penyedia",
)
async def get_provider_models(
    provider_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ModelProviderService, Depends(get_provider_service)],
    task_type: str = Query("llm", description="Tipe tugas (llm, embedding, atau rerank)"),
) -> ModelProviderValidateResponse:
    """
    Mengambil daftar model milik penyedia.

    Args:
        provider_id: ID penyedia.
        session: Session basis data.
        service: Layanan penyedia.

    Returns:
        Daftar model.

    Raises:
        HTTPException: Bila penyedia tidak ditemukan.
    """
    logger.info(f"Mengambil daftar model penyedia: {provider_id}")

    try:
        # Mengambil informasi penyedia
        provider = await service.get_provider_by_id(session, provider_id)

        # Penyedia bawaan tidak memerlukan API Key, langsung mengembalikan daftar model tetap
        if provider.is_builtin:
            models = await service.get_available_models(
                provider=provider,
                task_type=task_type,
            )
            enriched_models = await service.enrich_models_with_catalog_metadata(
                provider=provider,
                task_type=task_type,
                models=models,
            )
            return ModelProviderValidateResponse(
                success=True,
                message="Berhasil mengambil daftar model",
                models=[AvailableModel.model_validate(model) for model in enriched_models],
            )

        # Mengambil API Key yang sudah didekripsi
        api_key = service.get_decrypted_api_key(provider)
        if not api_key:
            # Memeriksa apakah field kosong atau dekripsi gagal
            has_encrypted_field = (
                provider.api_key_encrypted and provider.api_key_encrypted.strip() != ""
            )
            if has_encrypted_field:
                logger.warning(
                    f"Provider {provider_id} has encrypted API key but decryption failed. "
                    f"Field length: {len(provider.api_key_encrypted)}"
                )
                return ModelProviderValidateResponse(
                    success=False,
                    message="Gagal mendekripsi API Key, konfigurasikan ulang API Key penyedia ini",
                    models=[],
                )
            else:
                logger.info(f"Provider {provider_id} has no API key configured")
                return ModelProviderValidateResponse(
                    success=False,
                    message=(
                        "Penyedia ini belum mengonfigurasi API Key, tidak dapat mengambil daftar "
                        "model"
                    ),
                    models=[],
                )

        # Mencatat prefiks dan sufiks API key untuk keperluan debug (bagian tengah disembunyikan)
        if len(api_key) > 8:
            masked_key = f"{api_key[:4]}...{api_key[-4:]}"
        else:
            masked_key = "****"
        logger.debug(f"Using API key: {masked_key} (length: {len(api_key)})")

        # Mengambil daftar model (mengambil model LLM atau Embedding sesuai task_type)
        models = await service.get_available_models(
            provider=provider,
            task_type=task_type,
        )
        enriched_models = await service.enrich_models_with_catalog_metadata(
            provider=provider,
            task_type=task_type,
            models=models,
        )

        logger.info(f"Berhasil mengambil {len(models)} model")
        return ModelProviderValidateResponse(
            success=True,
            message="Berhasil mengambil daftar model" if models else "Penyedia ini mungkin tidak mendukung daftar model API",
            models=[AvailableModel.model_validate(model) for model in enriched_models],
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        # Memakai log berparameter dari loguru agar kurung kurawal di error_msg tidak dianggap placeholder format
        logger.error("Gagal mengambil daftar model: {}", error_msg, exc_info=True)
        return ModelProviderValidateResponse(
            success=False,
            message=f"Gagal mengambil daftar model: {error_msg}",
            models=[],
        )
