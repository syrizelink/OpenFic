# -*- coding: utf-8 -*-
"""
Prompt Chains Router - 提示词链 API。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.prompt_chain import (
    CreateVersionRequest,
    PromptChainVersionResponse,
    PromptEntryResponse,
    VersionWithEntriesResponse,
    PromptChainsMetadataResponse,
    CompiledEntryResponse,
    CompileResponse,
    VersionDiffResponse,
    EntryDiffResponse,
)
from app.core.errors import NotFoundError, ValidationError
from app.storage.database import get_session
from app.storage.services import prompt_chain_service
from app.storage.services.prompt_chain_service import PromptEntryData

router = APIRouter(prefix="/prompt-chains", tags=["prompt-chains"])


@router.get(
    "/metadata",
    response_model=PromptChainsMetadataResponse,
    summary="获取提示词链元数据",
)
async def get_metadata(
    session: AsyncSession = Depends(get_session),
) -> PromptChainsMetadataResponse:
    """
    获取所有提示词链的元数据,用于构建导航菜单。

    返回分层结构: mode > task > agent

    Args:
        session: 数据库session。

    Returns:
        元数据响应。
    """
    metadata = await prompt_chain_service.get_prompt_chains_metadata(session)
    return PromptChainsMetadataResponse.model_validate(metadata)


@router.get(
    "/{mode_name}/{task_name}/versions",
    response_model=list[PromptChainVersionResponse],
    summary="获取版本列表",
)
async def list_versions(
    mode_name: str,
    task_name: str,
    agent_name: str | None = Query(None, description="Agent名称（可选）"),
    active_only: bool = False,
    session: AsyncSession = Depends(get_session),
) -> list[PromptChainVersionResponse]:
    """
    获取提示词链的所有版本。

    默认状态（数据库中无记录）返回空列表。

    Args:
        mode_name: 模式名称。
        task_name: 任务名称。
        agent_name: Agent名称（可选）。
        active_only: 是否仅获取活跃版本。
        session: 数据库session。

    Returns:
        版本列表。
    """
    versions = await prompt_chain_service.list_versions(
        session, mode_name, task_name, agent_name, active_only
    )
    return [PromptChainVersionResponse.model_validate(v) for v in versions]


@router.get(
    "/{mode_name}/{task_name}/versions/latest",
    response_model=VersionWithEntriesResponse,
    summary="获取最新版本",
)
async def get_latest_version(
    mode_name: str,
    task_name: str,
    agent_name: str | None = Query(None, description="Agent名称（可选）"),
    session: AsyncSession = Depends(get_session),
) -> VersionWithEntriesResponse:
    """
    获取最新的活跃版本及其条目。

    如果数据库中没有用户创建的版本，返回 YAML 中的默认内容，
    此时 version.versionNumber 为 0 表示默认状态。

    Args:
        mode_name: 模式名称。
        task_name: 任务名称。
        agent_name: Agent名称（可选）。
        session: 数据库session。

    Returns:
        版本及其条目。
    """
    try:
        result = await prompt_chain_service.get_latest_version_with_entries_or_default(
            session, mode_name, task_name, agent_name
        )

        return VersionWithEntriesResponse(
            version=PromptChainVersionResponse.model_validate(result.version),
            entries=[PromptEntryResponse.model_validate(e) for e in result.entries],
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{mode_name}/{task_name}/versions/{version_id}",
    response_model=VersionWithEntriesResponse,
    summary="获取指定版本",
)
async def get_version(
    mode_name: str,
    task_name: str,
    version_id: str,
    agent_name: str | None = Query(None, description="Agent名称（可选）"),
    session: AsyncSession = Depends(get_session),
) -> VersionWithEntriesResponse:
    """
    获取指定版本及其条目。

    Args:
        mode_name: 模式名称。
        task_name: 任务名称。
        version_id: 版本ID。
        agent_name: Agent名称（可选）。
        session: 数据库session。

    Returns:
        版本及其条目。
    """
    try:
        result = await prompt_chain_service.get_version_with_entries(
            session, version_id
        )

        return VersionWithEntriesResponse(
            version=PromptChainVersionResponse.model_validate(result.version),
            entries=[PromptEntryResponse.model_validate(e) for e in result.entries],
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{mode_name}/{task_name}/versions",
    response_model=VersionWithEntriesResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建新版本",
)
async def create_version(
    mode_name: str,
    task_name: str,
    request: CreateVersionRequest,
    agent_name: str | None = Query(None, description="Agent名称（可选）"),
    session: AsyncSession = Depends(get_session),
) -> VersionWithEntriesResponse:
    """
    创建新版本。

    如果是第一次保存（parent_version_id 为 "default"），创建 v1。
    如果父版本不是最新版本，会将后续版本标记为非活跃。

    Args:
        mode_name: 模式名称。
        task_name: 任务名称。
        request: 创建请求。
        agent_name: Agent名称（可选）。
        session: 数据库session。

    Returns:
        新创建的版本及其条目。
    """
    try:
        is_first_save = request.parent_version_id == "default"

        if is_first_save:
            result = await prompt_chain_service.create_first_version(
                session, mode_name, task_name, agent_name,
                [PromptEntryData(**e.model_dump()) for e in request.entries],
                request.note
            )
        else:
            entries = [PromptEntryData(**e.model_dump()) for e in request.entries]
            result = await prompt_chain_service.create_new_version(
                session, mode_name, task_name, agent_name,
                request.parent_version_id, entries, request.note
            )

        await session.commit()

        logger.info(f"创建新版本: v{result.version.version_number}")

        return VersionWithEntriesResponse(
            version=PromptChainVersionResponse.model_validate(result.version),
            entries=[PromptEntryResponse.model_validate(e) for e in result.entries],
        )
    except NotFoundError as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await session.rollback()
        logger.error(f"创建版本失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建失败",
        )


@router.post(
    "/{mode_name}/{task_name}/compile",
    response_model=CompileResponse,
    summary="编译提示词链",
)
async def compile_prompt_chain(
    mode_name: str,
    task_name: str,
    agent_name: str | None = Query(None, description="Agent名称（可选）"),
    session: AsyncSession = Depends(get_session),
) -> CompileResponse:
    """
    编译提示词链。

    Args:
        mode_name: 模式名称。
        task_name: 任务名称。
        agent_name: Agent名称（可选）。
        session: 数据库session。

    Returns:
        编译后的提示词列表。
    """
    from app.macro.compiler import PromptChainCompiler, EntryInput

    try:
        result = await prompt_chain_service.get_latest_version_with_entries_or_default(
            session, mode_name, task_name, agent_name
        )

        entry_inputs = [
            EntryInput(
                role=e.role,
                content=e.content,
                order_index=e.order_index,
                is_enabled=e.is_enabled,
            )
            for e in result.entries
        ]

        compiler = PromptChainCompiler()
        compile_result = await compiler.compile(entries=entry_inputs)

        return CompileResponse(
            entries=[
                CompiledEntryResponse(
                    role=e.role,
                    content=e.content,
                    token_count=e.token_count,
                )
                for e in compile_result.entries
            ],
            total_tokens=compile_result.total_tokens,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"编译提示词链失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"编译失败: {str(e)}",
        )


@router.get(
    "/{mode_name}/{task_name}/versions/{version_id}/diff/{compare_version_id}",
    response_model=VersionDiffResponse,
    summary="对比两个版本的差异",
)
async def diff_versions(
    mode_name: str,
    task_name: str,
    version_id: str,
    compare_version_id: str,
    agent_name: str | None = Query(None, description="Agent名称（可选）"),
    session: AsyncSession = Depends(get_session),
) -> VersionDiffResponse:
    """
    对比两个版本之间的差异。

    Args:
        mode_name: 模式名称。
        task_name: 任务名称。
        version_id: 基准版本ID。
        compare_version_id: 对比版本ID。
        agent_name: Agent名称（可选）。
        session: 数据库session。

    Returns:
        版本差异信息。
    """

    try:
        base_result = await prompt_chain_service.get_version_with_entries(
            session, version_id
        )
        compare_result = await prompt_chain_service.get_version_with_entries(
            session, compare_version_id
        )

        base_entries_map = {e.uid: e for e in base_result.entries}
        compare_entries_map = {e.uid: e for e in compare_result.entries}

        diffs = []

        all_entry_uids = set(base_entries_map.keys()) | set(compare_entries_map.keys())

        for entry_uid in all_entry_uids:
            base_entry = base_entries_map.get(entry_uid)
            compare_entry = compare_entries_map.get(entry_uid)

            if base_entry and compare_entry:
                if (
                    base_entry.name != compare_entry.name
                    or base_entry.role != compare_entry.role
                    or base_entry.content != compare_entry.content
                    or base_entry.is_enabled != compare_entry.is_enabled
                    or base_entry.order_index != compare_entry.order_index
                ):
                    diffs.append(
                        EntryDiffResponse(
                            entry_id=entry_uid,
                            change_type="modified",
                            base_entry=PromptEntryResponse.model_validate(base_entry),
                            compare_entry=PromptEntryResponse.model_validate(
                                compare_entry
                            ),
                        )
                    )
            elif base_entry and not compare_entry:
                diffs.append(
                    EntryDiffResponse(
                        entry_id=entry_uid,
                        change_type="deleted",
                        base_entry=PromptEntryResponse.model_validate(base_entry),
                        compare_entry=None,
                    )
                )
            elif not base_entry and compare_entry:
                diffs.append(
                    EntryDiffResponse(
                        entry_id=entry_uid,
                        change_type="added",
                        base_entry=None,
                        compare_entry=PromptEntryResponse.model_validate(compare_entry),
                    )
                )

        return VersionDiffResponse(
            base_version=PromptChainVersionResponse.model_validate(base_result.version),
            compare_version=PromptChainVersionResponse.model_validate(
                compare_result.version
            ),
            diffs=diffs,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"对比版本失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"对比失败: {str(e)}",
        )


@router.post(
    "/{mode_name}/{task_name}/reset",
    response_model=VersionWithEntriesResponse,
    status_code=status.HTTP_200_OK,
    summary="重置提示词链到默认状态",
)
async def reset_to_default(
    mode_name: str,
    task_name: str,
    agent_name: str | None = Query(None, description="Agent名称（可选）"),
    session: AsyncSession = Depends(get_session),
) -> VersionWithEntriesResponse:
    """
    重置提示词链到默认状态。

    删除数据库中该类型提示词链的所有版本和条目，
    然后从 YAML 配置文件加载默认内容并返回内存默认版本。

    Args:
        mode_name: 模式名称。
        task_name: 任务名称。
        agent_name: Agent名称（可选）。
        session: 数据库session。

    Returns:
        重置后的版本及其条目。
    """
    try:
        result = await prompt_chain_service.reset_to_default(
            session, mode_name, task_name, agent_name
        )

        await session.commit()

        logger.info(
            f"重置提示词链到默认: {mode_name}/{task_name}"
            + (f"/{agent_name}" if agent_name else "")
        )

        return VersionWithEntriesResponse(
            version=PromptChainVersionResponse.model_validate(result.version),
            entries=[PromptEntryResponse.model_validate(e) for e in result.entries],
        )
    except NotFoundError as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        await session.rollback()
        logger.error(f"重置提示词链失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置失败: {str(e)}",
        )
