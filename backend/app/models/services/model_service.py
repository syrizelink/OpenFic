# -*- coding: utf-8 -*-
"""
Model Service - lapisan logika bisnis model.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.background.llm.resolver import resolve_background_llm
from app.core.errors import NotFoundError
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
    with_default,
)
from app.models.repos import model_repo
from app.storage.repos import retrieval_index_repo


class ModelService:
    """Service model."""

    async def get_all_models(self, session: AsyncSession) -> list[Model]:
        """
        Mengambil semua model.

        Args:
            session: session basis data.

        Returns:
            Daftar model.
        """
        return await model_repo.get_all(session)

    async def get_models_by_provider(
        self, session: AsyncSession, provider_id: str, task_type: str | None = None
    ) -> list[Model]:
        """
        Mengambil daftar model berdasarkan ID penyedia, opsional difilter task_type.

        Args:
            session: session basis data.
            provider_id: ID penyedia.
            task_type: filter jenis tugas opsional (llm, embedding, atau rerank).

        Returns:
            Daftar model.
        """
        models = await model_repo.get_by_provider_id(session, provider_id)
        if task_type:
            models = [m for m in models if m.task_type == task_type]
        return models

    async def get_model_by_id(self, session: AsyncSession, model_id: str) -> Model:
        """
        Mengambil model berdasarkan ID.

        Args:
            session: session basis data.
            model_id: ID model.

        Returns:
            Instance model.

        Raises:
            NotFoundError: jika model tidak ditemukan.
        """
        model = await model_repo.get_by_id(session, model_id)
        if not model:
            raise NotFoundError(f"Model with id {model_id} not found")
        return model

    async def validate_model_connection(
        self, session: AsyncSession, model_id: str
    ) -> None:
        """Mengirim satu permintaan non-streaming minimal untuk memvalidasi koneksi."""
        model = await self.get_model_by_id(session, model_id)
        if model.task_type != "llm":
            raise ValueError("Hanya mendukung validasi koneksi model bahasa")

        resolved = await resolve_background_llm(
            session,
            model_policy="model_validation",
            model_id=model_id,
        )
        await resolved.client.generate(
            [{"role": "user", "content": "hi"}],
            timeout=30,
        )

    async def create_model(
        self,
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
            temperature: parameter Temperature (LLM).
            top_p: parameter Top P (LLM).
            top_k: parameter Top K (LLM).
            min_p: parameter Min P (LLM).
            top_a: parameter Top A (LLM).
            frequency_penalty: parameter Frequency Penalty (LLM).
            presence_penalty: parameter Presence Penalty (LLM).
            repetition_penalty: parameter Repetition Penalty (LLM).
            max_tokens: parameter Max Tokens (LLM).
            dimensions: dimensi embedding (embedding).
        Returns:
            Instance model yang dibuat.
        """
        if await model_repo.exists_by_name(session, name):
            raise ValueError("Nama model sudah ada")

        if task_type != "llm":
            temperature = None
            top_p = None
            top_k = None
            min_p = None
            top_a = None
            frequency_penalty = None
            presence_penalty = None
            repetition_penalty = None
        else:
            temperature = with_default(temperature, DEFAULT_TEMPERATURE)
            top_p = with_default(top_p, DEFAULT_TOP_P)
            top_k = with_default(top_k, DEFAULT_TOP_K)
            min_p = with_default(min_p, DEFAULT_MIN_P)
            top_a = with_default(top_a, DEFAULT_TOP_A)
            frequency_penalty = with_default(
                frequency_penalty, DEFAULT_FREQUENCY_PENALTY
            )
            presence_penalty = with_default(presence_penalty, DEFAULT_PRESENCE_PENALTY)
            repetition_penalty = with_default(
                repetition_penalty, DEFAULT_REPETITION_PENALTY
            )

        model = await model_repo.create(
            session=session,
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
        await session.commit()
        return model

    async def update_model(
        self,
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
    ) -> Model:
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
            Instance model setelah diperbarui.

        Raises:
            NotFoundError: jika model tidak ditemukan.
        """
        existing = await self.get_model_by_id(session, model_id)
        if existing.is_builtin:
            raise ValueError("Model bawaan tidak boleh diedit")
        if name is not None and await model_repo.exists_by_name(
            session, name, exclude_model_id=model_id
        ):
            raise ValueError("Nama model sudah ada")
        if await retrieval_index_repo.exists_by_embedding_model_ref_id(
            session, model_id
        ):
            protected_changes = []
            if provider_id is not None and provider_id != existing.provider_id:
                protected_changes.append("provider_id")
            if model_identifier is not None and model_identifier != existing.model_id:
                protected_changes.append("model_id")
            if dimensions is not None and dimensions != existing.dimensions:
                protected_changes.append("dimensions")
            if protected_changes:
                raise ValueError(
                    "Embedding model is bound to retrieval indexes; cannot change "
                    + ", ".join(protected_changes)
                )

        model = await model_repo.update(
            session=session,
            model_id=model_id,
            name=name,
            remark=remark,
            provider_id=provider_id,
            model_identifier=model_identifier,
            task_type=task_type,
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

        if not model:
            raise NotFoundError(f"Model with id {model_id} not found")

        await session.commit()
        return model

    async def delete_model(self, session: AsyncSession, model_id: str) -> None:
        """
        Menghapus model.

        Args:
            session: session basis data.
            model_id: ID model.

        Raises:
            NotFoundError: jika model tidak ditemukan.
            ValueError: jika model adalah model bawaan, tidak boleh dihapus.
        """
        model = await model_repo.get_by_id(session, model_id)
        if not model:
            raise NotFoundError(f"Model with id {model_id} not found")
        if model.is_builtin:
            raise ValueError("Model bawaan tidak boleh dihapus")
        success = await model_repo.delete_by_id(session, model_id)
        if not success:
            raise NotFoundError(f"Model with id {model_id} not found")
        await session.commit()
