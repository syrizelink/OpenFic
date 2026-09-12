# -*- coding: utf-8 -*-
"""
Model Repository - lapisan akses data model.
"""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.models.entities.model import Model
from app.models.clients.model_params import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_FREQUENCY_PENALTY,
    DEFAULT_MIN_P,
    DEFAULT_PRESENCE_PENALTY,
    DEFAULT_REPETITION_PENALTY,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_A,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
)
from app.models.entities.model_provider import ModelProvider


async def get_all(session: AsyncSession) -> list[Model]:
    """
    Mengambil semua model.

    Args:
        session: session basis data.

    Returns:
        Daftar model.
    """
    result = await session.execute(select(Model))
    return list(result.scalars().all())


async def get_by_provider_id(session: AsyncSession, provider_id: str) -> list[Model]:
    """
    Mengambil daftar model berdasarkan ID penyedia.

    Args:
        session: session basis data.
        provider_id: ID penyedia.

    Returns:
        Daftar model.
    """
    result = await session.execute(
        select(Model).where(col(Model.provider_id) == provider_id)
    )
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, model_id: str) -> Model | None:
    """
    Mengambil model berdasarkan ID.

    Args:
        session: session basis data.
        model_id: ID model.

    Returns:
        Instance model, atau None jika tidak ditemukan.
    """
    result = await session.execute(select(Model).where(col(Model.id) == model_id))
    return result.scalar_one_or_none()


async def exists_by_name(
    session: AsyncSession, name: str, *, exclude_model_id: str | None = None
) -> bool:
    """Memeriksa apakah ada model dengan nama sama, model yang sedang diedit dapat dikecualikan."""
    statement = select(col(Model.id)).where(col(Model.name) == name)
    if exclude_model_id is not None:
        statement = statement.where(col(Model.id) != exclude_model_id)
    result = await session.execute(statement.limit(1))
    return result.scalar_one_or_none() is not None


async def get_by_legacy_agent_config(
    session: AsyncSession,
    *,
    model_id: str,
    provider_type: str,
    base_url: str,
) -> Model | None:
    """Find the unique current model matching a checkpoint created before model IDs persisted."""
    result = await session.execute(
        select(Model)
        .join(ModelProvider, col(Model.provider_id) == col(ModelProvider.id))
        .where(
            col(Model.model_id) == model_id,
            col(ModelProvider.provider_type) == provider_type,
            col(ModelProvider.url) == base_url,
        )
    )
    matches = list(result.scalars().all())
    return matches[0] if len(matches) == 1 else None


async def create(
    session: AsyncSession,
    name: str,
    provider_id: str,
    model_id: str,
    task_type: str = "llm",
    remark: str = "",
    temperature: float | None = DEFAULT_TEMPERATURE,
    top_p: float | None = DEFAULT_TOP_P,
    top_k: int | None = DEFAULT_TOP_K,
    min_p: float | None = DEFAULT_MIN_P,
    top_a: float | None = DEFAULT_TOP_A,
    frequency_penalty: float | None = DEFAULT_FREQUENCY_PENALTY,
    presence_penalty: float | None = DEFAULT_PRESENCE_PENALTY,
    repetition_penalty: float | None = DEFAULT_REPETITION_PENALTY,
    max_tokens: int | None = None,
    context_length: int = DEFAULT_CONTEXT_LENGTH,
    input_price: float = 0.0,
    output_price: float = 0.0,
    cache_read_price: float = 0.0,
    cache_write_price: float = 0.0,
    dimensions: int | None = None,
) -> Model:
    """
    Membuat model.

    Args:
        session: session basis data.
        name: nama model.
        provider_id: ID penyedia yang terkait.
        model_id: ID model yang diperoleh dari penyedia.
        task_type: jenis tugas (llm, embedding, atau rerank).
        remark: catatan.
        temperature: parameter Temperature.
        top_p: parameter Top P.
        top_k: parameter Top K.
        min_p: parameter Min P.
        top_a: parameter Top A.
        frequency_penalty: parameter Frequency Penalty.
        presence_penalty: parameter Presence Penalty.
        repetition_penalty: parameter Repetition Penalty.
        max_tokens: parameter Max Tokens.
        dimensions: dimensi embedding.
    Returns:
        Instance model yang dibuat.
    """
    model = Model(
        name=name,
        provider_id=provider_id,
        model_id=model_id,
        task_type=task_type,
        remark=remark,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        min_p=min_p,
        top_a=top_a,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        repetition_penalty=repetition_penalty,
        max_tokens=max_tokens,
        context_length=context_length,
        input_price=input_price,
        output_price=output_price,
        cache_read_price=cache_read_price,
        cache_write_price=cache_write_price,
        dimensions=dimensions,
    )
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model


async def update(
    session: AsyncSession,
    model_id: str,
    name: str | None = None,
    remark: str | None = None,
    provider_id: str | None = None,
    model_identifier: str | None = None,
    task_type: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    min_p: float | None = None,
    top_a: float | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
    repetition_penalty: float | None = None,
    max_tokens: int | None = None,
    context_length: int | None = None,
    input_price: float | None = None,
    output_price: float | None = None,
    cache_read_price: float | None = None,
    cache_write_price: float | None = None,
    dimensions: int | None = None,
) -> Model | None:
    """
    Memperbarui model.

    Args:
        session: session basis data.
        model_id: ID model.
        name: nama model.
        remark: catatan.
        provider_id: ID penyedia yang terkait.
        model_identifier: ID model yang diperoleh dari penyedia.
        task_type: jenis tugas.
        temperature: parameter Temperature.
        top_p: parameter Top P.
        top_k: parameter Top K.
        min_p: parameter Min P.
        top_a: parameter Top A.
        frequency_penalty: parameter Frequency Penalty.
        presence_penalty: parameter Presence Penalty.
        repetition_penalty: parameter Repetition Penalty.
        max_tokens: parameter Max Tokens.
        dimensions: dimensi embedding.
    Returns:
        Instance model setelah diperbarui, atau None jika tidak ditemukan.
    """
    model = await get_by_id(session, model_id)
    if not model:
        return None

    if name is not None:
        model.name = name
    if remark is not None:
        model.remark = remark
    if provider_id is not None:
        model.provider_id = provider_id
    if model_identifier is not None:
        model.model_id = model_identifier
    if task_type is not None:
        model.task_type = task_type
    if temperature is not None:
        model.temperature = temperature
    if top_p is not None:
        model.top_p = top_p
    if top_k is not None:
        model.top_k = top_k
    if min_p is not None:
        model.min_p = min_p
    if top_a is not None:
        model.top_a = top_a
    if frequency_penalty is not None:
        model.frequency_penalty = frequency_penalty
    if presence_penalty is not None:
        model.presence_penalty = presence_penalty
    if repetition_penalty is not None:
        model.repetition_penalty = repetition_penalty
    if max_tokens is not None:
        model.max_tokens = max_tokens
    if context_length is not None:
        model.context_length = context_length
    if input_price is not None:
        model.input_price = input_price
    if output_price is not None:
        model.output_price = output_price
    if cache_read_price is not None:
        model.cache_read_price = cache_read_price
    if cache_write_price is not None:
        model.cache_write_price = cache_write_price
    if dimensions is not None:
        model.dimensions = dimensions

    model.updated_at = datetime.now(UTC)
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model


async def delete_by_id(session: AsyncSession, model_id: str) -> bool:
    """
    Menghapus model.

    Args:
        session: session basis data.
        model_id: ID model.

    Returns:
        Apakah penghapusan berhasil.
    """
    result = await session.execute(delete(Model).where(col(Model.id) == model_id))
    return cast("CursorResult[Any]", result).rowcount > 0
