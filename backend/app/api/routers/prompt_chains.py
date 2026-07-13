# -*- coding: utf-8 -*-
"""提示词链 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.prompt_chain import (
    CompiledEntryResponse,
    CompileResponse,
    CreateVersionRequest,
    EntryDiffResponse,
    PromptChainVersionResponse,
    PromptChainsMetadataResponse,
    PromptEntryResponse,
    PromptEntrySearchMatch,
    PromptEntrySearchResponse,
    PromptEntrySearchResult,
    VersionDiffResponse,
    VersionWithEntriesResponse,
)
from app.core.errors import NotFoundError, ValidationError
from app.macro.compiler import EntryInput, PromptChainCompiler
from app.storage.database import get_session
from app.storage.services import prompt_chain_service
from app.storage.services.prompt_chain_service import PromptEntryData

router = APIRouter(prefix="/prompt-chains", tags=["prompt-chains"])


def _version_response(result: prompt_chain_service.VersionWithEntries) -> VersionWithEntriesResponse:
    return VersionWithEntriesResponse(
        version=PromptChainVersionResponse.model_validate(result.version),
        entries=[PromptEntryResponse.model_validate(entry) for entry in result.entries],
    )


@router.get("/categories", response_model=PromptChainsMetadataResponse, summary="获取提示词分类")
async def get_categories(
    session: AsyncSession = Depends(get_session),
) -> PromptChainsMetadataResponse:
    metadata = await prompt_chain_service.get_prompt_chains_metadata(session)
    return PromptChainsMetadataResponse.model_validate(metadata)


@router.get("/{prompt_id}/versions", response_model=list[PromptChainVersionResponse], summary="获取版本列表")
async def list_versions(
    prompt_id: str,
    active_only: bool = False,
    session: AsyncSession = Depends(get_session),
) -> list[PromptChainVersionResponse]:
    versions = await prompt_chain_service.list_versions(session, prompt_id, active_only)
    return [PromptChainVersionResponse.model_validate(version) for version in versions]


@router.get("/{prompt_id}/versions/latest", response_model=VersionWithEntriesResponse, summary="获取最新版本")
async def get_latest_version(
    prompt_id: str,
    session: AsyncSession = Depends(get_session),
) -> VersionWithEntriesResponse:
    try:
        result = await prompt_chain_service.get_latest_version_with_entries_or_default(session, prompt_id)
        return _version_response(result)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{prompt_id}/versions/{version_id}", response_model=VersionWithEntriesResponse, summary="获取指定版本")
async def get_version(
    prompt_id: str,
    version_id: str,
    session: AsyncSession = Depends(get_session),
) -> VersionWithEntriesResponse:
    try:
        result = await prompt_chain_service.get_version_with_entries(session, version_id, prompt_id)
        if result.version.prompt_id != prompt_id:
            raise NotFoundError(f"版本不属于提示词链: {prompt_id}")
        return _version_response(result)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{prompt_id}/versions/{version_id}/search",
    response_model=PromptEntrySearchResponse,
    summary="搜索提示词版本条目",
)
async def search_version_entries(
    prompt_id: str,
    version_id: str,
    q: Annotated[str, Query(min_length=1, description="搜索关键词")],
    session: AsyncSession = Depends(get_session),
) -> PromptEntrySearchResponse:
    """搜索指定提示词版本的条目名称和内容。"""
    try:
        result = await prompt_chain_service.search_version_entries(session, prompt_id, version_id, q)
        return PromptEntrySearchResponse(
            results=[
                PromptEntrySearchResult(
                    entry_id=item.entry_id,
                    entry_name=item.entry_name,
                    role=item.role,
                    matches=[
                        PromptEntrySearchMatch(
                            line_number=match.line_number,
                            line_text=match.line_text,
                        )
                        for match in item.matches
                    ],
                )
                for item in result.results
            ],
            total_entries=result.total_entries,
            total_matches=result.total_matches,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{prompt_id}/versions",
    response_model=VersionWithEntriesResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建新版本",
)
async def create_version(
    prompt_id: str,
    request: CreateVersionRequest,
    session: AsyncSession = Depends(get_session),
) -> VersionWithEntriesResponse:
    try:
        entries = [PromptEntryData(**entry.model_dump()) for entry in request.entries]
        if request.parent_version_id == "default":
            result = await prompt_chain_service.create_first_version(session, prompt_id, entries, request.note)
        else:
            result = await prompt_chain_service.create_new_version(
                session,
                prompt_id,
                request.parent_version_id,
                entries,
                request.note,
            )
        await session.commit()
        logger.info(f"创建提示词版本: prompt_id={prompt_id}, version={result.version.version_number}")
        return _version_response(result)
    except (NotFoundError, ValidationError) as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        await session.rollback()
        logger.exception(f"创建提示词版本失败: prompt_id={prompt_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建失败") from exc


@router.post("/{prompt_id}/compile", response_model=CompileResponse, summary="编译提示词链")
async def compile_prompt_chain(
    prompt_id: str,
    session: AsyncSession = Depends(get_session),
) -> CompileResponse:
    try:
        result = await prompt_chain_service.get_latest_version_with_entries_or_default(session, prompt_id)
        compiler = PromptChainCompiler()
        enabled_entries = sorted(
            (entry for entry in result.entries if entry.is_enabled),
            key=lambda entry: entry.order_index,
        )
        compiled = await compiler.compile(
            [
                EntryInput(
                    role=entry.role,
                    content=entry.content,
                    order_index=entry.order_index,
                    is_enabled=entry.is_enabled,
                )
                for entry in enabled_entries
            ]
        )
        return CompileResponse(
            entries=[
                CompiledEntryResponse(
                    name=source_entry.name,
                    role=compiled_entry.role,
                    content=compiled_entry.content,
                    token_count=compiled_entry.token_count,
                )
                for source_entry, compiled_entry in zip(enabled_entries, compiled.entries, strict=True)
            ],
            total_tokens=compiled.total_tokens,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{prompt_id}/versions/{version_id}/diff/{compare_version_id}",
    response_model=VersionDiffResponse,
    summary="对比两个版本的差异",
)
async def diff_versions(
    prompt_id: str,
    version_id: str,
    compare_version_id: str,
    session: AsyncSession = Depends(get_session),
) -> VersionDiffResponse:
    try:
        base_result = await prompt_chain_service.get_version_with_entries(session, version_id, prompt_id)
        compare_result = await prompt_chain_service.get_version_with_entries(
            session, compare_version_id, prompt_id
        )
        if base_result.version.prompt_id != prompt_id or compare_result.version.prompt_id != prompt_id:
            raise NotFoundError(f"版本不属于提示词链: {prompt_id}")

        base_entries = {entry.uid: entry for entry in base_result.entries}
        compare_entries = {entry.uid: entry for entry in compare_result.entries}
        diffs = []
        for entry_uid in set(base_entries) | set(compare_entries):
            base_entry = base_entries.get(entry_uid)
            compare_entry = compare_entries.get(entry_uid)
            if base_entry and compare_entry:
                if any(
                    getattr(base_entry, field) != getattr(compare_entry, field)
                    for field in ("name", "role", "content", "is_enabled", "order_index")
                ):
                    diffs.append(
                        EntryDiffResponse(
                            entry_id=entry_uid,
                            change_type="modified",
                            base_entry=PromptEntryResponse.model_validate(base_entry),
                            compare_entry=PromptEntryResponse.model_validate(compare_entry),
                        )
                    )
            elif base_entry:
                diffs.append(
                    EntryDiffResponse(
                        entry_id=entry_uid,
                        change_type="deleted",
                        base_entry=PromptEntryResponse.model_validate(base_entry),
                        compare_entry=None,
                    )
                )
            elif compare_entry:
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
            compare_version=PromptChainVersionResponse.model_validate(compare_result.version),
            diffs=diffs,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{prompt_id}/reset", response_model=VersionWithEntriesResponse, summary="重置提示词链")
async def reset_to_default(
    prompt_id: str,
    session: AsyncSession = Depends(get_session),
) -> VersionWithEntriesResponse:
    try:
        result = await prompt_chain_service.reset_to_default(session, prompt_id)
        await session.commit()
        return _version_response(result)
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
