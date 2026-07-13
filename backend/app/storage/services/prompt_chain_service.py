# -*- coding: utf-8 -*-
"""
PromptChain Service - 提示词链业务逻辑层。
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
    """提示词条目数据传输对象。"""
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
    """版本及其条目数据。"""
    version: PromptChainVersion
    entries: list[PromptEntry]


@dataclass
class PromptEntrySearchMatch:
    """提示词条目中的单行搜索命中。"""

    line_number: int
    line_text: str


@dataclass
class PromptEntrySearchResult:
    """单个提示词条目的搜索结果。"""

    entry_id: str
    entry_name: str
    role: str
    matches: list[PromptEntrySearchMatch]


@dataclass
class PromptEntrySearchResponse:
    """提示词版本内条目搜索结果。"""

    results: list[PromptEntrySearchResult]
    total_entries: int
    total_matches: int


def _build_custom_agent_default_entries(kind: str) -> list[PromptEntryData]:
    if kind == "primary":
        system_content = (
            "你是一个主智能体，负责协调和调度子智能体完成复杂任务。"
            "请根据任务需求规划并委派工作。"
        )
    else:
        system_content = (
            "你是一个子智能体，负责执行主智能体委派的具体任务。"
            "请专注于完成当前分配的工作。"
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
            content="请开始执行任务。",
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
        raise NotFoundError(f"提示词链不存在: {prompt_id}")
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
    获取版本及其所有条目。

    Raises:
        NotFoundError: 版本不存在。
    """
    if version_id == "default":
        if prompt_id is None:
            raise ValidationError("获取默认版本时必须指定 prompt_id")
        return _load_default_version_with_entries(prompt_id)

    version = await prompt_chain_version_repo.get_by_id(session, version_id)
    if version is None:
        raise NotFoundError(f"版本不存在: {version_id}")

    entries = await prompt_entry_repo.list_by_version(session, version_id)
    return VersionWithEntries(version=version, entries=entries)


async def search_version_entries(
    session: AsyncSession,
    prompt_id: str,
    version_id: str,
    query: str,
) -> PromptEntrySearchResponse:
    """搜索指定提示词版本中的条目名称和内容。"""
    result = await get_version_with_entries(session, version_id, prompt_id)
    if result.version.prompt_id != prompt_id:
        raise NotFoundError(f"版本不属于提示词链: {prompt_id}")

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
    获取最新的活跃版本。

    Raises:
        NotFoundError: 没有活跃版本。
    """
    version = await prompt_chain_version_repo.get_latest_version(session, prompt_id)
    if version is None:
        raise NotFoundError(f"没有找到活跃版本: {prompt_id}")
    return version


async def list_versions(
    session: AsyncSession,
    prompt_id: str,
    active_only: bool = False
) -> list[PromptChainVersion]:
    """获取提示词链的所有版本。"""
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
    创建第一个用户版本（v1）。

    从默认状态保存时调用此函数，创建第一个版本。

    Args:
        session: 数据库session。
        prompt_id: 提示词唯一标识。
        entries: 条目列表。
        note: 版本备注。

    Returns:
        新创建的版本及其条目。
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
    """为自定义智能体创建首个默认提示词版本。"""
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
    创建新版本。

    如果父版本不是最新版本，会将后续版本标记为非活跃。

    Args:
        session: 数据库session。
        prompt_id: 提示词唯一标识。
        parent_version_id: 父版本ID。
        entries: 条目列表。
        note: 版本备注。

    Returns:
        新创建的版本及其条目。
    """
    import uuid

    parent_version = await prompt_chain_version_repo.get_by_id(session, parent_version_id)
    if parent_version is None:
        raise NotFoundError(f"父版本不存在: {parent_version_id}")

    if parent_version.prompt_id != prompt_id:
        raise ValidationError("父版本不属于该提示词链")

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
    更新条目。

    注意：这个操作不会创建新版本，只更新现有条目。
    如果需要版本控制，应该使用create_new_version。
    """
    entry = await prompt_entry_repo.get_by_id(session, entry_id)
    if entry is None:
        raise NotFoundError(f"条目不存在: {entry_id}")

    if name is not None:
        entry.name = name
    if role is not None:
        if role not in ("system", "user", "assistant"):
            raise ValidationError(f"无效的角色类型: {role}")
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
    删除条目。

    注意：这个操作不会创建新版本，直接删除条目。
    如果需要版本控制，应该通过create_new_version排除该条目。
    """
    entry = await prompt_entry_repo.get_by_id(session, entry_id)
    if entry is None:
        raise NotFoundError(f"条目不存在: {entry_id}")

    return await prompt_entry_repo.delete_by_id(session, entry_id)


async def get_prompt_chains_metadata(session: AsyncSession) -> dict:
    """
    获取所有提示词链的元数据，用于构建导航菜单。

    元数据从 YAML 配置文件读取，并合入数据库中的自定义 agent key。

    返回按业务类别分组的单级提示词列表。
    """
    from app.prompts import get_prompt_chains_metadata as get_yaml_metadata
    from app.storage.repos import agent_definition_repo

    custom_agents: list[tuple[str, str]] = []
    records = await agent_definition_repo.list_all(session)
    for record in records:
        if record.source == "custom" and record.key not in (
            "primary",
            "explorer",
            "composer",
            "auditor",
            "writer",
            "actor",
            "reviewer",
        ):
            custom_agents.append((record.key, record.display_name))

    return get_yaml_metadata(custom_agents=custom_agents)


async def reset_to_default(
    session: AsyncSession,
    prompt_id: str,
) -> VersionWithEntries:
    """
    重置提示词链到默认状态。

    删除数据库中该类型提示词链的所有版本和条目，
    然后从 YAML 文件加载默认内容并返回内存默认版本。

    Args:
        session: 数据库session。
        prompt_id: 提示词唯一标识。

    Returns:
        重置后的内存默认版本及其条目。

    Raises:
        NotFoundError: YAML 配置文件不存在。
    """
    from app.prompts import load_prompt_chain

    default_entries = load_prompt_chain(prompt_id)
    if default_entries is None:
        raise NotFoundError(f"默认提示词配置不存在: {prompt_id}")

    await prompt_chain_version_repo.delete_by_chain_key(session, prompt_id)

    return _default_version_with_entries(prompt_id, default_entries)


async def delete_prompt_chain(
    session: AsyncSession,
    prompt_id: str,
) -> int:
    """删除指定提示词链的所有版本和条目。"""
    return await prompt_chain_version_repo.delete_by_chain_key(session, prompt_id)
