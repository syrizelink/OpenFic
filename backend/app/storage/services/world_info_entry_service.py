# -*- coding: utf-8 -*-
"""
WorldInfo Entry Service - lapisan logika bisnis entri buku dunia.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.editor_content_limits import validate_editor_content
from app.core.errors import NotFoundError
from app.core.utils.tiktoken import get_encoding
from app.storage.models.world_info_entry import WorldInfoEntry
from app.storage.repos import world_info_entry_repo
from app.storage.services.world_info_service import get_world_info


class WorldInfoEntryNameConflictError(ValueError):
    """Konflik nama entri buku dunia."""


@dataclass
class WorldInfoImportEntry:
    """Entri impor buku dunia setelah dinormalisasi."""

    uid: int
    name: str
    content: str
    is_enabled: bool
    order: int


@dataclass
class WorldInfoImportPreviewResult:
    """Hasil pratinjau impor buku dunia."""

    entries: list[WorldInfoImportEntry]


@dataclass
class WorldInfoImportResult:
    """Hasil impor buku dunia."""

    world_info_id: str
    imported_count: int


@dataclass
class WorldInfoEntrySearchMatch:
    """Item yang cocok pada pencarian."""

    line_number: int
    line_text: str


@dataclass
class WorldInfoEntrySearchResult:
    """Hasil pencarian satu entri."""

    entry_id: str
    entry_name: str
    uid: int
    matches: list[WorldInfoEntrySearchMatch]


@dataclass
class WorldInfoEntrySearchResponse:
    """Respons pencarian."""

    results: list[WorldInfoEntrySearchResult]
    total_entries: int
    total_matches: int


def _build_entry_name(comment: object, uid: int) -> str:
    """Menghasilkan nama entri berdasarkan comment."""
    if isinstance(comment, str):
        comment_clean = comment.strip()
        if comment_clean:
            return comment_clean[:200]
    return f"Entri {uid}"


def _calculate_token_count(content: str) -> int:
    """Menghitung jumlah token isi entri."""
    try:
        return len(get_encoding("cl100k_base").encode(content))
    except Exception:
        return len(content) // 4


async def _get_existing_entry_names(
    session: AsyncSession,
    world_info_id: str,
    exclude_entry_id: str | None = None,
) -> set[str]:
    entries = await world_info_entry_repo.list_all_by_world_info(session, world_info_id)
    return {entry.name for entry in entries if entry.id != exclude_entry_id}


def generate_unique_entry_name(base_name: str, existing_names: set[str]) -> str:
    normalized_name = base_name.strip()
    if normalized_name not in existing_names:
        return normalized_name

    counter = 1
    while f"{normalized_name} ({counter})" in existing_names:
        counter += 1
    return f"{normalized_name} ({counter})"


async def ensure_entry_name_available(
    session: AsyncSession,
    world_info_id: str,
    name: str,
    exclude_entry_id: str | None = None,
) -> str:
    normalized_name = name.strip()
    existing_names = await _get_existing_entry_names(
        session, world_info_id, exclude_entry_id=exclude_entry_id
    )
    if normalized_name in existing_names:
        raise WorldInfoEntryNameConflictError(f"Nama entri buku dunia sudah ada: {normalized_name}")
    return normalized_name


def parse_sillytavern_worldbook(raw_payload: bytes) -> WorldInfoImportPreviewResult:
    """Mem-parsing JSON buku dunia SillyTavern dan menormalisasinya ke struktur proyek ini."""
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("Enkode file tidak valid, gunakan file JSON berenkode UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Parsing JSON gagal, periksa format file ekspor buku dunia") from exc

    if not isinstance(payload, dict):
        raise ValueError("Format file buku dunia tidak valid: tingkat teratas harus berupa objek")

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, dict):
        raise ValueError("Format file buku dunia tidak valid: objek entries tidak ada")

    entries: list[WorldInfoImportEntry] = []
    for entry_key, raw_entry in raw_entries.items():
        if not isinstance(raw_entry, dict):
            continue

        raw_uid = raw_entry.get("uid")
        if isinstance(raw_uid, bool):
            uid = 0
        elif isinstance(raw_uid, int):
            uid = raw_uid
        else:
            try:
                uid = int(entry_key)
            except (TypeError, ValueError):
                uid = len(entries)

        content = raw_entry.get("content")
        content_text = content if isinstance(content, str) else ""
        comment = raw_entry.get("comment")
        disable = bool(raw_entry.get("disable", False))
        order = raw_entry.get("order")
        order_value = order if isinstance(order, int) else uid + 1

        entries.append(
            WorldInfoImportEntry(
                uid=uid,
                name=_build_entry_name(comment, uid),
                content=content_text,
                is_enabled=not disable,
                order=order_value,
            )
        )

    if not entries:
        raise ValueError("Tidak ada entri yang dapat diimpor di dalam buku dunia")

    entries.sort(key=lambda entry: (entry.order, entry.uid))
    return WorldInfoImportPreviewResult(entries=entries)


async def import_entries(
    session: AsyncSession,
    world_info_id: str,
    entries: list[WorldInfoImportEntry],
    mode: str = "append",
) -> WorldInfoImportResult:
    """Mengimpor entri buku dunia secara massal."""
    await get_world_info(session, world_info_id)

    if mode not in {"append", "overwrite"}:
        raise ValueError(f"Mode impor tidak didukung: {mode}")

    for entry in entries:
        validate_editor_content(entry.content)

    if mode == "overwrite":
        await world_info_entry_repo.delete_by_world_info(session, world_info_id)
        existing_entries: list[WorldInfoEntry] = []
    else:
        existing_entries = await world_info_entry_repo.list_all_by_world_info(session, world_info_id)

    existing_by_name = {entry.name: entry for entry in existing_entries}
    max_uid = await world_info_entry_repo.get_max_uid(session, world_info_id)
    max_order = await world_info_entry_repo.get_max_order(session, world_info_id)

    imported_count = 0
    for entry in entries:
        token_count = _calculate_token_count(entry.content)
        existing = existing_by_name.get(entry.name)
        if existing is not None:
            existing.content = entry.content
            existing.token_count = token_count
            existing.is_enabled = entry.is_enabled
            existing.updated_at = datetime.now(UTC)
            await world_info_entry_repo.update_entry(session, existing)
            imported_count += 1
            continue

        max_uid += 1
        max_order += 1
        created = await world_info_entry_repo.create(
            session,
            WorldInfoEntry(
                world_info_id=world_info_id,
                uid=max_uid,
                name=entry.name,
                order=max_order,
                content=entry.content,
                token_count=token_count,
                is_enabled=entry.is_enabled,
            ),
        )
        existing_by_name[created.name] = created
        imported_count += 1

    return WorldInfoImportResult(
        world_info_id=world_info_id,
        imported_count=imported_count,
    )


# ============== Operasi entri buku dunia ==============


async def create_entry(
    session: AsyncSession,
    world_info_id: str,
    name: str,
    content: str = "",
    token_count: int = 0,
    is_enabled: bool = True,
) -> WorldInfoEntry:
    """
    Membuat entri buku dunia.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.
        name: Nama entri.
        content: Isi entri.
        token_count: Jumlah Token.
        is_enabled: Status aktif.

    Returns:
        Instance entri yang dibuat.

    Raises:
        NotFoundError: Buku dunia tidak ditemukan.
    """
    validate_editor_content(content)

    # Memeriksa apakah buku dunia ada
    await get_world_info(session, world_info_id)

    existing_names = await _get_existing_entry_names(session, world_info_id)
    unique_name = generate_unique_entry_name(name, existing_names)

    # Mengambil UID dan order terbesar saat ini
    max_uid = await world_info_entry_repo.get_max_uid(session, world_info_id)
    max_order = await world_info_entry_repo.get_max_order(session, world_info_id)

    entry = WorldInfoEntry(
        world_info_id=world_info_id,
        uid=max_uid + 1,
        name=unique_name,
        order=max_order + 1,
        content=content,
        token_count=token_count,
        is_enabled=is_enabled,
    )
    return await world_info_entry_repo.create(session, entry)


async def get_entry(session: AsyncSession, entry_id: str) -> WorldInfoEntry:
    """
    Mengambil entri buku dunia.

    Args:
        session: session basis data.
        entry_id: ID entri.

    Returns:
        Instance entri.

    Raises:
        NotFoundError: Entri tidak ditemukan.
    """
    entry = await world_info_entry_repo.get_by_id(session, entry_id)
    if entry is None:
        raise NotFoundError(f"Entri tidak ditemukan: {entry_id}")
    return entry


async def list_entries(
    session: AsyncSession,
    world_info_id: str,
) -> list[WorldInfoEntry]:
    """
    Mengambil daftar entri buku dunia.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.
    Returns:
        Daftar entri.

    Raises:
        NotFoundError: Buku dunia tidak ditemukan.
    """
    # Memeriksa apakah buku dunia ada
    await get_world_info(session, world_info_id)

    return await world_info_entry_repo.list_all_by_world_info(session, world_info_id)


async def update_entry(
    session: AsyncSession,
    entry_id: str,
    name: str | None = None,
    content: str | None = None,
    token_count: int | None = None,
    is_enabled: bool | None = None,
) -> WorldInfoEntry:
    """
    Memperbarui entri buku dunia.

    Args:
        session: session basis data.
        entry_id: ID entri.
        name: Nama baru.
        content: Isi baru.
        token_count: Jumlah Token baru.
        is_enabled: Status aktif baru.

    Returns:
        Instance entri setelah diperbarui.

    Raises:
        NotFoundError: Entri tidak ditemukan.
    """
    entry = await get_entry(session, entry_id)

    if name is not None:
        entry.name = await ensure_entry_name_available(
            session,
            entry.world_info_id,
            name,
            exclude_entry_id=entry.id,
        )
    if content is not None:
        validate_editor_content(content)
        entry.content = content
    if token_count is not None:
        entry.token_count = token_count
    if is_enabled is not None:
        entry.is_enabled = is_enabled

    entry.updated_at = datetime.now(UTC)
    return await world_info_entry_repo.update_entry(session, entry)


async def delete_all_entries(session: AsyncSession, world_info_id: str) -> int:
    """
    Menghapus semua entri buku dunia.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.

    Returns:
        Jumlah entri yang dihapus.
    """
    await get_world_info(session, world_info_id)
    entries = await world_info_entry_repo.list_all_by_world_info(session, world_info_id)
    count = len(entries)
    await world_info_entry_repo.delete_by_world_info(session, world_info_id)
    return count


async def delete_entry(session: AsyncSession, entry_id: str) -> None:
    """
    Menghapus entri buku dunia, lalu menyesuaikan order entri berikutnya.

    Args:
        session: session basis data.
        entry_id: ID entri.

    Raises:
        NotFoundError: Entri tidak ditemukan.
    """
    entry = await get_entry(session, entry_id)
    old_order = entry.order
    world_info_id = entry.world_info_id

    # Menghapus entri
    await world_info_entry_repo.delete(session, entry)

    # Mengurangi 1 pada order entri berikutnya
    max_order = await world_info_entry_repo.get_max_order(session, world_info_id)
    if old_order < max_order:
        await world_info_entry_repo.shift_orders(
            session, world_info_id, old_order + 1, max_order, -1
        )


async def move_entry(
    session: AsyncSession,
    entry_id: str,
    new_order: int,
) -> WorldInfoEntry:
    """
    Memindahkan entri buku dunia ke posisi baru.

    Args:
        session: session basis data.
        entry_id: ID entri.
        new_order: Posisi urutan baru.

    Returns:
        Instance entri setelah diperbarui.

    Raises:
        NotFoundError: Entri tidak ditemukan.
        ValueError: Posisi baru tidak valid.
    """
    entry = await get_entry(session, entry_id)
    old_order = entry.order
    world_info_id = entry.world_info_id

    if new_order < 1:
        raise ValueError("Posisi urutan harus lebih besar dari 0")

    max_order = await world_info_entry_repo.get_max_order(session, world_info_id)
    if new_order > max_order:
        new_order = max_order

    if old_order == new_order:
        return entry

    # Menyesuaikan order entri lain
    if new_order < old_order:
        # Pindah ke depan: order entri pada [new_order, old_order) +1
        await world_info_entry_repo.shift_orders(
            session, world_info_id, new_order, old_order - 1, 1
        )
    else:
        # Pindah ke belakang: order entri pada (old_order, new_order] -1
        await world_info_entry_repo.shift_orders(
            session, world_info_id, old_order + 1, new_order, -1
        )

    entry.order = new_order
    entry.updated_at = datetime.now(UTC)
    return await world_info_entry_repo.update_entry(session, entry)


async def toggle_entry(session: AsyncSession, entry_id: str) -> WorldInfoEntry:
    """
    Mengalihkan status aktif entri buku dunia.

    Args:
        session: session basis data.
        entry_id: ID entri.

    Returns:
        Instance entri setelah diperbarui.

    Raises:
        NotFoundError: Entri tidak ditemukan.
    """
    entry = await get_entry(session, entry_id)
    entry.is_enabled = not entry.is_enabled
    entry.updated_at = datetime.now(UTC)
    return await world_info_entry_repo.update_entry(session, entry)


async def batch_toggle_entries(
    session: AsyncSession,
    world_info_id: str,
    entry_ids: list[str],
    is_enabled: bool,
) -> int:
    """Mengalihkan status aktif entri secara massal."""
    await get_world_info(session, world_info_id)
    updated = await world_info_entry_repo.batch_toggle(
        session, world_info_id, entry_ids, is_enabled
    )
    return updated


async def batch_delete_entries(
    session: AsyncSession,
    world_info_id: str,
    entry_ids: list[str],
) -> int:
    """Menghapus entri secara massal."""
    await get_world_info(session, world_info_id)
    deleted = await world_info_entry_repo.batch_delete(
        session, world_info_id, entry_ids
    )
    return deleted


async def search_entries(
    session: AsyncSession,
    world_info_id: str,
    query: str,
) -> WorldInfoEntrySearchResponse:
    await get_world_info(session, world_info_id)

    if not query.strip():
        return WorldInfoEntrySearchResponse(results=[], total_entries=0, total_matches=0)

    entries = await world_info_entry_repo.search_by_content(
        session, world_info_id, query
    )

    results: list[WorldInfoEntrySearchResult] = []
    total_matches = 0
    lower_query = query.lower()

    for entry in entries:
        lines = entry.content.split("\n")
        matches: list[WorldInfoEntrySearchMatch] = []
        for line_number, line in enumerate(lines, start=1):
            if lower_query in line.lower():
                matches.append(
                    WorldInfoEntrySearchMatch(
                        line_number=line_number,
                        line_text=line,
                    )
                )

        if matches:
            results.append(
                WorldInfoEntrySearchResult(
                    entry_id=entry.id,
                    entry_name=entry.name,
                    uid=entry.uid,
                    matches=matches,
                )
            )
            total_matches += len(matches)

    return WorldInfoEntrySearchResponse(
        results=results,
        total_entries=len(results),
        total_matches=total_matches,
    )
