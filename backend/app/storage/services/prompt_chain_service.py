# -*- coding: utf-8 -*-
"""
PromptChain Service - lapisan logika bisnis rantai prompt.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.storage.models.prompt_chain_version import PromptChainVersion, generate_short_hash
from app.storage.models.prompt_entry import PromptEntry
from app.storage.repos import (
    prompt_chain_version_repo,
    prompt_entry_repo,
)


@dataclass
class PromptEntryData:
    """Objek transfer data entri prompt."""
    id: str | None = None
    uid: str | None = None
    name: str = ""
    role: str = "user"
    content: str = ""
    order_index: int = 0
    is_enabled: bool = True
    token_count: int = 0


@dataclass
class VersionWithEntries:
    """Data versi beserta entri-entrinya."""
    version: PromptChainVersion
    entries: list[PromptEntry]


@dataclass
class PromptEntrySearchMatch:
    """Kecocokan pencarian per baris di dalam entri prompt."""

    line_number: int
    line_text: str


@dataclass
class PromptEntrySearchResult:
    """Hasil pencarian satu entri prompt."""

    entry_id: str
    entry_name: str
    role: str
    matches: list[PromptEntrySearchMatch]


@dataclass
class PromptEntrySearchResponse:
    """Hasil pencarian entri di dalam versi prompt."""

    results: list[PromptEntrySearchResult]
    total_entries: int
    total_matches: int


def _build_custom_agent_default_entries(kind: str) -> list[PromptEntryData]:
    if kind == "primary":
        system_content = (
            "Anda adalah agen utama yang mengoordinasi dan menjadwalkan"
            " subagen untuk menyelesaikan tugas kompleks."
            "Rencanakan dan delegasikan pekerjaan sesuai kebutuhan tugas."
        )
    else:
        system_content = (
            "Anda adalah subagen yang menjalankan tugas konkret yang didelegasikan agen utama."
            "Fokuslah menyelesaikan pekerjaan yang sedang ditugaskan."
        )

    return [
        PromptEntryData(
            name="system_prompt",
            role="system",
            content=system_content,
            order_index=0,
            is_enabled=True,
            token_count=0,
        ),
        PromptEntryData(
            name="user_prompt",
            role="user",
            content="Silakan mulai menjalankan tugas.",
            order_index=1,
            is_enabled=True,
            token_count=0,
        ),
    ]


def _default_version_with_entries(
    prompt_id: str,
    entries: list[PromptEntryData],
) -> VersionWithEntries:
    """Build an in-memory default version without writing to DB."""
    now = datetime.now(UTC)
    version = PromptChainVersion(
        id="default",
        prompt_id=prompt_id,
        version_hash="default",
        version_number=0,
        parent_version_id=None,
        is_active=True,
        note=None,
        created_at=now,
    )
    prompt_entries = [
        PromptEntry(
            id=f"default-{index}",
            uid=entry.uid or f"default-uid-{index}",
            version_id="default",
            name=entry.name,
            role=entry.role,
            content=entry.content,
            order_index=entry.order_index,
            is_enabled=entry.is_enabled,
            token_count=entry.token_count,
            created_at=now,
            updated_at=now,
        )
        for index, entry in enumerate(entries)
    ]
    return VersionWithEntries(version=version, entries=prompt_entries)


def _load_default_version_with_entries(prompt_id: str) -> VersionWithEntries:
    from app.prompts import load_prompt_chain

    default_entries = load_prompt_chain(prompt_id)
    if default_entries is None:
        raise NotFoundError(f"Rantai prompt tidak ditemukan: {prompt_id}")
    return _default_version_with_entries(prompt_id, default_entries)


async def get_latest_version_with_entries_or_default(
    session: AsyncSession,
    prompt_id: str,
) -> VersionWithEntries:
    """Get the active DB version, falling back to YAML defaults without persistence."""
    version = await prompt_chain_version_repo.get_latest_version(session, prompt_id)
    if version is not None:
        return await get_version_with_entries(session, version.id)

    return _load_default_version_with_entries(prompt_id)


async def get_version_with_entries(
    session: AsyncSession,
    version_id: str,
    prompt_id: str | None = None,
) -> VersionWithEntries:
    """
    Mengambil versi beserta seluruh entrinya.

    Raises:
        NotFoundError: Versi tidak ditemukan.
    """
    if version_id == "default":
        if prompt_id is None:
            raise ValidationError("prompt_id harus ditentukan saat mengambil versi default")
        return _load_default_version_with_entries(prompt_id)

    version = await prompt_chain_version_repo.get_by_id(session, version_id)
    if version is None:
        raise NotFoundError(f"Versi tidak ditemukan: {version_id}")

    entries = await prompt_entry_repo.list_by_version(session, version_id)
    return VersionWithEntries(version=version, entries=entries)


async def search_version_entries(
    session: AsyncSession,
    prompt_id: str,
    version_id: str,
    query: str,
) -> PromptEntrySearchResponse:
    """Mencari nama dan isi entri di dalam versi prompt tertentu."""
    result = await get_version_with_entries(session, version_id, prompt_id)
    if result.version.prompt_id != prompt_id:
        raise NotFoundError(f"Versi bukan milik rantai prompt: {prompt_id}")

    stripped_query = query.strip()
    if not stripped_query:
        return PromptEntrySearchResponse(results=[], total_entries=0, total_matches=0)

    lower_query = stripped_query.lower()
    results: list[PromptEntrySearchResult] = []
    total_matches = 0

    for entry in result.entries:
        matches = [
            PromptEntrySearchMatch(line_number=line_number, line_text=line)
            for line_number, line in enumerate(entry.content.split("\n"), start=1)
            if lower_query in line.lower()
        ]
        if lower_query in entry.name.lower():
            matches.insert(0, PromptEntrySearchMatch(line_number=0, line_text=entry.name))
        if matches:
            results.append(
                PromptEntrySearchResult(
                    entry_id=entry.id,
                    entry_name=entry.name,
                    role=entry.role,
                    matches=matches,
                )
            )
            total_matches += len(matches)

    return PromptEntrySearchResponse(
        results=results,
        total_entries=len(results),
        total_matches=total_matches,
    )


async def get_latest_version(
    session: AsyncSession,
    prompt_id: str,
) -> PromptChainVersion:
    """
    Mengambil versi aktif terbaru.

    Raises:
        NotFoundError: Tidak ada versi aktif.
    """
    version = await prompt_chain_version_repo.get_latest_version(session, prompt_id)
    if version is None:
        raise NotFoundError(f"Versi aktif tidak ditemukan: {prompt_id}")
    return version


async def list_versions(
    session: AsyncSession,
    prompt_id: str,
    active_only: bool = False
) -> list[PromptChainVersion]:
    """Mengambil semua versi dari rantai prompt."""
    versions = await prompt_chain_version_repo.list_by_chain_key(
        session, prompt_id, active_only
    )
    if prompt_id.startswith("custom-agent--"):
        return versions

    try:
        default_version = _load_default_version_with_entries(prompt_id).version
    except NotFoundError:
        return versions
    return [*versions, default_version]


async def create_first_version(
    session: AsyncSession,
    prompt_id: str,
    entries: list[PromptEntryData],
    note: str | None = None,
) -> VersionWithEntries:
    """
    Membuat versi pengguna pertama (v1).

    Fungsi ini dipanggil saat menyimpan dari keadaan default, membuat versi pertama.

    Args:
        session: session basis data.
        prompt_id: Identitas unik prompt.
        entries: Daftar entri.
        note: Catatan versi.

    Returns:
        Versi yang baru dibuat beserta entrinya.
    """
    import uuid

    new_version = PromptChainVersion(
        prompt_id=prompt_id,
        version_hash=generate_short_hash(),
        version_number=1,
        parent_version_id=None,
        is_active=True,
        note=note,
    )
    new_version = await prompt_chain_version_repo.create(session, new_version)

    now = datetime.now(UTC)
    new_entries = []
    for entry_data in entries:
        entry_uid = entry_data.uid if entry_data.uid else str(uuid.uuid4())

        entry = PromptEntry(
            uid=entry_uid,
            version_id=new_version.id,
            name=entry_data.name,
            role=entry_data.role,
            content=entry_data.content,
            order_index=entry_data.order_index,
            is_enabled=entry_data.is_enabled,
            token_count=entry_data.token_count,
            created_at=now,
            updated_at=now,
        )
        new_entries.append(entry)

    created_entries = await prompt_entry_repo.create_many(session, new_entries)

    return VersionWithEntries(version=new_version, entries=created_entries)


async def create_initial_custom_agent_version(
    session: AsyncSession,
    agent_name: str,
    kind: str,
) -> VersionWithEntries:
    """Membuat versi prompt default pertama untuk agen kustom."""
    return await create_first_version(
        session,
        f"custom-agent--{agent_name}",
        _build_custom_agent_default_entries(kind),
    )


async def create_new_version(
    session: AsyncSession,
    prompt_id: str,
    parent_version_id: str,
    entries: list[PromptEntryData],
    note: str | None = None,
) -> VersionWithEntries:
    """
    Membuat versi baru.

    Bila versi induk bukan versi terbaru, versi-versi setelahnya ditandai tidak aktif.

    Args:
        session: session basis data.
        prompt_id: Identitas unik prompt.
        parent_version_id: ID versi induk.
        entries: Daftar entri.
        note: Catatan versi.

    Returns:
        Versi yang baru dibuat beserta entrinya.
    """
    import uuid

    parent_version = await prompt_chain_version_repo.get_by_id(session, parent_version_id)
    if parent_version is None:
        raise NotFoundError(f"Versi induk tidak ditemukan: {parent_version_id}")

    if parent_version.prompt_id != prompt_id:
        raise ValidationError("Versi induk bukan milik rantai prompt ini")

    max_version_number = await prompt_chain_version_repo.get_max_version_number(
        session, prompt_id
    )
    new_version_number = max_version_number + 1

    if parent_version.version_number < max_version_number:
        await prompt_chain_version_repo.deactivate_versions_after(
            session, prompt_id, parent_version.version_number
        )

    now = datetime.now(UTC)

    new_version = PromptChainVersion(
        prompt_id=prompt_id,
        version_hash=generate_short_hash(),
        version_number=new_version_number,
        parent_version_id=parent_version_id,
        is_active=True,
        note=note,
    )
    new_version = await prompt_chain_version_repo.create(session, new_version)

    new_entries = []
    for entry_data in entries:
        entry_uid = entry_data.uid if entry_data.uid else str(uuid.uuid4())

        entry = PromptEntry(
            uid=entry_uid,
            version_id=new_version.id,
            name=entry_data.name,
            role=entry_data.role,
            content=entry_data.content,
            order_index=entry_data.order_index,
            is_enabled=entry_data.is_enabled,
            token_count=entry_data.token_count,
            created_at=now,
            updated_at=now,
        )
        new_entries.append(entry)

    created_entries = await prompt_entry_repo.create_many(session, new_entries)

    return VersionWithEntries(version=new_version, entries=created_entries)


async def update_entry(
    session: AsyncSession,
    entry_id: str,
    name: str | None = None,
    role: str | None = None,
    content: str | None = None,
    order_index: int | None = None,
    is_enabled: bool | None = None,
    token_count: int | None = None,
) -> PromptEntry:
    """
    Memperbarui entri.

    Catatan: operasi ini tidak membuat versi baru, hanya memperbarui entri yang ada.
    Bila kontrol versi dibutuhkan, gunakan create_new_version.
    """
    entry = await prompt_entry_repo.get_by_id(session, entry_id)
    if entry is None:
        raise NotFoundError(f"Entri tidak ditemukan: {entry_id}")

    if name is not None:
        entry.name = name
    if role is not None:
        if role not in ("system", "user", "assistant"):
            raise ValidationError(f"Jenis peran tidak valid: {role}")
        entry.role = role
    if content is not None:
        entry.content = content
    if order_index is not None:
        entry.order_index = order_index
    if is_enabled is not None:
        entry.is_enabled = is_enabled
    if token_count is not None:
        entry.token_count = token_count

    entry.updated_at = datetime.now(UTC)
    return await prompt_entry_repo.update(session, entry)


async def delete_entry(
    session: AsyncSession,
    entry_id: str,
) -> bool:
    """
    Menghapus entri.

    Catatan: operasi ini tidak membuat versi baru, entri langsung dihapus.
    Bila kontrol versi dibutuhkan, kecualikan entri tersebut melalui create_new_version.
    """
    entry = await prompt_entry_repo.get_by_id(session, entry_id)
    if entry is None:
        raise NotFoundError(f"Entri tidak ditemukan: {entry_id}")

    return await prompt_entry_repo.delete_by_id(session, entry_id)


async def get_prompt_chains_metadata(session: AsyncSession) -> dict:
    """
    Mengambil metadata semua rantai prompt, untuk membangun menu navigasi.

    Metadata dibaca dari file konfigurasi YAML, lalu digabung dengan agent key kustom di basis data.

    Mengembalikan daftar prompt satu tingkat yang dikelompokkan menurut kategori bisnis.
    """
    from app.agent_runtime.agents.definitions import DEFAULT_AGENT_KEYS
    from app.prompts import get_prompt_chains_metadata as get_yaml_metadata
    from app.storage.repos import agent_definition_repo

    custom_agents: list[tuple[str, str]] = []
    records = await agent_definition_repo.list_all(session)
    for record in records:
        if record.source == "custom" and record.key not in DEFAULT_AGENT_KEYS:
            custom_agents.append((record.key, record.display_name))

    return get_yaml_metadata(custom_agents=custom_agents)


async def reset_to_default(
    session: AsyncSession,
    prompt_id: str,
) -> VersionWithEntries:
    """
    Mereset rantai prompt ke keadaan default.

    Menghapus semua versi dan entri rantai prompt jenis tersebut di basis data,
    lalu memuat isi default dari file YAML dan mengembalikan versi default di memori.

    Args:
        session: session basis data.
        prompt_id: Identitas unik prompt.

    Returns:
        Versi default di memori setelah reset beserta entrinya.

    Raises:
        NotFoundError: File konfigurasi YAML tidak ditemukan.
    """
    from app.prompts import load_prompt_chain

    default_entries = load_prompt_chain(prompt_id)
    if default_entries is None:
        raise NotFoundError(f"Konfigurasi prompt default tidak ditemukan: {prompt_id}")

    await prompt_chain_version_repo.delete_by_chain_key(session, prompt_id)

    return _default_version_with_entries(prompt_id, default_entries)


async def delete_prompt_chain(
    session: AsyncSession,
    prompt_id: str,
) -> int:
    """Menghapus semua versi dan entri dari rantai prompt tertentu."""
    return await prompt_chain_version_repo.delete_by_chain_key(session, prompt_id)
