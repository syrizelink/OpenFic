# -*- coding: utf-8 -*-
"""
WorldInfo Entry Service - 世界书条目业务逻辑层。
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import tiktoken
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.models.world_info_entry import WorldInfoEntry
from app.storage.repos import world_info_entry_repo
from app.storage.services.world_info_service import get_world_info


@dataclass
class WorldInfoEntryListResult:
    """世界书条目列表结果。"""

    items: list[WorldInfoEntry]
    total: int
    page: int
    page_size: int


@dataclass
class WorldInfoImportEntry:
    """归一化后的世界书导入条目。"""

    uid: int
    name: str
    content: str
    is_enabled: bool
    order: int


@dataclass
class WorldInfoImportPreviewResult:
    """世界书导入预览结果。"""

    entries: list[WorldInfoImportEntry]


@dataclass
class WorldInfoImportResult:
    """世界书导入结果。"""

    world_info_id: str
    imported_count: int


@dataclass
class WorldInfoEntrySearchMatch:
    """搜索匹配项。"""

    line_number: int
    line_text: str


@dataclass
class WorldInfoEntrySearchResult:
    """单个条目的搜索结果。"""

    entry_id: str
    entry_name: str
    uid: int
    matches: list[WorldInfoEntrySearchMatch]


@dataclass
class WorldInfoEntrySearchResponse:
    """搜索响应。"""

    results: list[WorldInfoEntrySearchResult]
    total_entries: int
    total_matches: int


def _build_entry_name(comment: object, uid: int) -> str:
    """根据 comment 生成条目名称。"""
    if isinstance(comment, str):
        comment_clean = comment.strip()
        if comment_clean:
            return comment_clean[:200]
    return f"条目 {uid}"


def _calculate_token_count(content: str) -> int:
    """计算条目内容的 token 数。"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(content))
    except Exception:
        return len(content) // 4


def parse_sillytavern_worldbook(raw_payload: bytes) -> WorldInfoImportPreviewResult:
    """解析 SillyTavern 世界书 JSON 并归一化为当前项目结构。"""
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("文件编码无效，请使用 UTF-8 编码的 JSON 文件") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("JSON 解析失败，请检查世界书导出文件格式") from exc

    if not isinstance(payload, dict):
        raise ValueError("世界书文件格式无效：顶层必须是对象")

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, dict):
        raise ValueError("世界书文件格式无效：缺少 entries 对象")

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
        raise ValueError("世界书中没有可导入的条目")

    entries.sort(key=lambda entry: (entry.order, entry.uid))
    return WorldInfoImportPreviewResult(entries=entries)


async def import_entries(
    session: AsyncSession,
    world_info_id: str,
    entries: list[WorldInfoImportEntry],
) -> WorldInfoImportResult:
    """批量导入世界书条目。"""
    await get_world_info(session, world_info_id)

    max_uid = await world_info_entry_repo.get_max_uid(session, world_info_id)
    max_order = await world_info_entry_repo.get_max_order(session, world_info_id)

    entry_objects: list[WorldInfoEntry] = []
    for index, entry in enumerate(entries, start=1):
        entry_objects.append(
            WorldInfoEntry(
                world_info_id=world_info_id,
                uid=max_uid + index,
                name=entry.name,
                order=max_order + index,
                content=entry.content,
                token_count=_calculate_token_count(entry.content),
                is_enabled=entry.is_enabled,
            )
        )

    session.add_all(entry_objects)
    await session.flush()

    return WorldInfoImportResult(
        world_info_id=world_info_id,
        imported_count=len(entry_objects),
    )


# ============== 世界书条目操作 ==============


async def create_entry(
    session: AsyncSession,
    world_info_id: str,
    name: str,
    content: str = "",
    token_count: int = 0,
    is_enabled: bool = True,
) -> WorldInfoEntry:
    """
    创建世界书条目。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。
        name: 条目名称。
        content: 条目内容。
        token_count: Token 数量。
        is_enabled: 开关状态。

    Returns:
        创建的条目实例。

    Raises:
        NotFoundError: 世界书不存在。
    """
    # 检查世界书是否存在
    await get_world_info(session, world_info_id)

    # 获取当前最大 UID 和 order
    max_uid = await world_info_entry_repo.get_max_uid(session, world_info_id)
    max_order = await world_info_entry_repo.get_max_order(session, world_info_id)

    entry = WorldInfoEntry(
        world_info_id=world_info_id,
        uid=max_uid + 1,
        name=name,
        order=max_order + 1,
        content=content,
        token_count=token_count,
        is_enabled=is_enabled,
    )
    return await world_info_entry_repo.create(session, entry)


async def get_entry(session: AsyncSession, entry_id: str) -> WorldInfoEntry:
    """
    获取世界书条目。

    Args:
        session: 数据库 session。
        entry_id: 条目 ID。

    Returns:
        条目实例。

    Raises:
        NotFoundError: 条目不存在。
    """
    entry = await world_info_entry_repo.get_by_id(session, entry_id)
    if entry is None:
        raise NotFoundError(f"条目不存在: {entry_id}")
    return entry


async def list_entries(
    session: AsyncSession,
    world_info_id: str,
    page: int = 1,
    page_size: int = 100,
) -> WorldInfoEntryListResult:
    """
    获取世界书条目列表。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。
        page: 页码（从 1 开始）。
        page_size: 每页数量。

    Returns:
        条目列表结果。

    Raises:
        NotFoundError: 世界书不存在。
    """
    # 检查世界书是否存在
    await get_world_info(session, world_info_id)

    offset = (page - 1) * page_size
    items = await world_info_entry_repo.list_by_world_info(
        session, world_info_id, offset=offset, limit=page_size
    )
    total = await world_info_entry_repo.count_by_world_info(session, world_info_id)
    return WorldInfoEntryListResult(
        items=items, total=total, page=page, page_size=page_size
    )


async def update_entry(
    session: AsyncSession,
    entry_id: str,
    name: str | None = None,
    content: str | None = None,
    token_count: int | None = None,
    is_enabled: bool | None = None,
) -> WorldInfoEntry:
    """
    更新世界书条目。

    Args:
        session: 数据库 session。
        entry_id: 条目 ID。
        name: 新名称。
        content: 新内容。
        token_count: 新 Token 数量。
        is_enabled: 新开关状态。

    Returns:
        更新后的条目实例。

    Raises:
        NotFoundError: 条目不存在。
    """
    entry = await get_entry(session, entry_id)

    if name is not None:
        entry.name = name
    if content is not None:
        entry.content = content
    if token_count is not None:
        entry.token_count = token_count
    if is_enabled is not None:
        entry.is_enabled = is_enabled

    entry.updated_at = datetime.now(UTC)
    return await world_info_entry_repo.update_entry(session, entry)


async def delete_all_entries(session: AsyncSession, world_info_id: str) -> int:
    """
    删除世界书的所有条目。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。

    Returns:
        删除的条目数量。
    """
    await get_world_info(session, world_info_id)
    entries = await world_info_entry_repo.list_by_world_info(session, world_info_id)
    count = len(entries)
    await world_info_entry_repo.delete_by_world_info(session, world_info_id)
    return count


async def delete_entry(session: AsyncSession, entry_id: str) -> None:
    """
    删除世界书条目，并调整后续条目的 order。

    Args:
        session: 数据库 session。
        entry_id: 条目 ID。

    Raises:
        NotFoundError: 条目不存在。
    """
    entry = await get_entry(session, entry_id)
    old_order = entry.order
    world_info_id = entry.world_info_id

    # 删除条目
    await world_info_entry_repo.delete(session, entry)

    # 将后续条目的 order 减 1
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
    移动世界书条目到新位置。

    Args:
        session: 数据库 session。
        entry_id: 条目 ID。
        new_order: 新排序位置。

    Returns:
        更新后的条目实例。

    Raises:
        NotFoundError: 条目不存在。
        ValueError: 新位置无效。
    """
    entry = await get_entry(session, entry_id)
    old_order = entry.order
    world_info_id = entry.world_info_id

    if new_order < 1:
        raise ValueError("排序位置必须大于 0")

    max_order = await world_info_entry_repo.get_max_order(session, world_info_id)
    if new_order > max_order:
        new_order = max_order

    if old_order == new_order:
        return entry

    # 调整其他条目的 order
    if new_order < old_order:
        # 向前移动：[new_order, old_order) 的条目 order +1
        await world_info_entry_repo.shift_orders(
            session, world_info_id, new_order, old_order - 1, 1
        )
    else:
        # 向后移动：(old_order, new_order] 的条目 order -1
        await world_info_entry_repo.shift_orders(
            session, world_info_id, old_order + 1, new_order, -1
        )

    entry.order = new_order
    entry.updated_at = datetime.now(UTC)
    return await world_info_entry_repo.update_entry(session, entry)


async def reorder_entries(
    session: AsyncSession,
    world_info_id: str,
    orders: dict[str, int],
) -> list[WorldInfoEntry]:
    """
    批量重新排序世界书条目。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。
        orders: 条目ID到新排序位置的映射。

    Returns:
        更新后的条目列表，按新顺序排序。

    Raises:
        NotFoundError: 条目不存在。
        ValueError: 排序位置无效。
    """
    if not orders:
        # 如果没有需要更新的条目，返回所有条目
        return await world_info_entry_repo.list_by_world_info(
            session, world_info_id, offset=0, limit=10000
        )

    # 验证所有条目ID是否存在且属于该世界书
    entry_ids = list(orders.keys())
    entries = await world_info_entry_repo.list_by_world_info(
        session, world_info_id, offset=0, limit=10000
    )
    entry_map = {entry.id: entry for entry in entries}

    for entry_id in entry_ids:
        if entry_id not in entry_map:
            raise NotFoundError(f"条目 {entry_id} 不存在")

    # 验证排序位置是否有效（1到条目总数）
    max_order = len(entries)
    for entry_id, new_order in orders.items():
        if new_order < 1:
            raise ValueError(f"条目 {entry_id} 的排序位置必须大于 0")
        if new_order > max_order:
            raise ValueError(f"条目 {entry_id} 的排序位置不能大于 {max_order}")

    # 批量更新所有条目的 order
    # 使用临时值避免冲突：先将所有需要更新的条目设置为临时值（负数）
    temp_start = -1000000
    for i, entry_id in enumerate(entry_ids):
        entry = entry_map[entry_id]
        entry.order = temp_start - i
        entry.updated_at = datetime.now(UTC)

    await session.flush()

    # 然后设置为最终值
    for entry_id, new_order in orders.items():
        entry = entry_map[entry_id]
        entry.order = new_order
        entry.updated_at = datetime.now(UTC)

    await session.flush()

    # 刷新所有条目以获取最新状态
    for entry in entries:
        await session.refresh(entry)

    # 返回所有条目，按新顺序排序
    all_entries = await world_info_entry_repo.list_by_world_info(
        session, world_info_id, offset=0, limit=10000
    )
    return sorted(all_entries, key=lambda e: e.order)


async def toggle_entry(session: AsyncSession, entry_id: str) -> WorldInfoEntry:
    """
    切换世界书条目的开关状态。

    Args:
        session: 数据库 session。
        entry_id: 条目 ID。

    Returns:
        更新后的条目实例。

    Raises:
        NotFoundError: 条目不存在。
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
    """批量切换条目启用状态。"""
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
    """批量删除条目。"""
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
