# -*- coding: utf-8 -*-
"""
Settings Router - 用户设置 API。
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools.permission_metadata import (
    SETTING_KEY_AGENT_BYPASS_TOOL_APPROVAL,
    SETTING_KEY_AGENT_TOOL_PERMISSIONS,
    get_default_agent_tool_permissions,
)
from app.agent_runtime.session_activity import has_active_agent_sessions
from app.api.agent_settings_lock import require_agent_settings_unlocked
from app.api.schemas.setting import (
    AgentSettingsLockResponse,
    AgentToolPermissionItem,
    AuditDetailsStorageResponse,
    ClearAuditDetailsResponse,
    SettingsResponse,
    SettingsUpdateRequest,
)
from app.audit.queue import (
    AUDIT_DETAILS_PERSISTENCE_SETTING_KEY,
    set_audit_details_persistence,
)
from app.audit.repo import LLMAuditLogRepo
from app.retrieval.chapter_index import (
    DEFAULT_INDEX_AUTO_STRATEGY,
    DEFAULT_INDEX_CHUNK_OVERLAP,
    DEFAULT_INDEX_CHUNK_SIZE,
    DEFAULT_INDEX_MODE,
    DEFAULT_INDEX_RERANK_ENABLED,
    DEFAULT_INDEX_RERANK_MODEL,
    SETTING_KEY_INDEX_AUTO_STRATEGY,
    SETTING_KEY_INDEX_CHUNK_OVERLAP,
    SETTING_KEY_INDEX_CHUNK_SIZE,
    SETTING_KEY_INDEX_ENABLED_PROJECTS,
    SETTING_KEY_INDEX_MODE,
    SETTING_KEY_INDEX_RERANK_ENABLED,
    SETTING_KEY_DEFAULT_RERANK_MODEL,
    _VALID_INDEX_AUTO_STRATEGIES,
    _VALID_INDEX_MODES,
)
from app.retrieval.index_status import schedule_emit_index_config
from app.storage.database import get_session
from app.storage.repos import (
    retrieval_chapter_index_state_repo,
    retrieval_index_repo,
    setting_repo,
)

router = APIRouter(prefix="/settings", tags=["settings"])

# 设置键名常量
SETTING_KEY_LANGUAGE = "language"
SETTING_KEY_THEME = "theme"
SETTING_KEY_FONT_FAMILY = "font_family"
SETTING_KEY_CODE_FONT_FAMILY = "code_font_family"
SETTING_KEY_DEFAULT_MODEL = "default_model"
SETTING_KEY_LIGHT_MODEL = "light_model"
SETTING_KEY_DEFAULT_EMBEDDING_MODEL = "default_embedding_model"
SETTING_KEY_AUDIT_PERSIST_DETAILS = AUDIT_DETAILS_PERSISTENCE_SETTING_KEY
# 默认值
DEFAULT_SETTINGS = {
    SETTING_KEY_LANGUAGE: "zh-CN",
    SETTING_KEY_THEME: "light",
    SETTING_KEY_FONT_FAMILY: "SourceHanSerifCN-VF",
    SETTING_KEY_CODE_FONT_FAMILY: "JetBrainsMapleMono",
    SETTING_KEY_DEFAULT_MODEL: "",
    SETTING_KEY_LIGHT_MODEL: "",
    SETTING_KEY_DEFAULT_EMBEDDING_MODEL: "",
    SETTING_KEY_INDEX_MODE: DEFAULT_INDEX_MODE,
    SETTING_KEY_INDEX_ENABLED_PROJECTS: "[]",
    SETTING_KEY_INDEX_CHUNK_SIZE: str(DEFAULT_INDEX_CHUNK_SIZE),
    SETTING_KEY_INDEX_CHUNK_OVERLAP: str(DEFAULT_INDEX_CHUNK_OVERLAP),
    SETTING_KEY_INDEX_AUTO_STRATEGY: DEFAULT_INDEX_AUTO_STRATEGY,
    SETTING_KEY_INDEX_RERANK_ENABLED: json.dumps(
        DEFAULT_INDEX_RERANK_ENABLED, ensure_ascii=False
    ),
    SETTING_KEY_DEFAULT_RERANK_MODEL: DEFAULT_INDEX_RERANK_MODEL,
    SETTING_KEY_AGENT_BYPASS_TOOL_APPROVAL: "false",
    SETTING_KEY_AGENT_TOOL_PERMISSIONS: "[]",
    SETTING_KEY_AUDIT_PERSIST_DETAILS: "false",
}


@router.get(
    "/agent-session-lock",
    response_model=AgentSettingsLockResponse,
    summary="获取 Agent 会话设置锁定状态",
)
async def get_agent_settings_lock(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentSettingsLockResponse:
    return AgentSettingsLockResponse(
        is_locked=await has_active_agent_sessions(session),
    )


def _parse_agent_tool_permissions(raw_value: str) -> list[AgentToolPermissionItem]:
    if not raw_value:
        return []

    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        logger.warning("agent_tool_permissions 配置不是合法 JSON，已回退为空列表")
        return []

    if not isinstance(payload, list):
        logger.warning("agent_tool_permissions 配置不是列表，已回退为空列表")
        return []

    result: list[AgentToolPermissionItem] = []
    for item in payload:
        try:
            result.append(AgentToolPermissionItem.model_validate(item))
        except Exception:
            logger.warning("agent_tool_permissions 存在非法项，已跳过")
    return result


def _parse_bool_setting(raw_value: str | None, *, default: bool = False) -> bool:
    if raw_value is None or raw_value == "":
        return default

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        normalized = raw_value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        logger.warning("布尔设置值非法，已回退到默认值")
        return default

    if isinstance(parsed, bool):
        return parsed
    if isinstance(parsed, (int, float)):
        return bool(parsed)

    logger.warning("布尔设置值类型非法，已回退到默认值")
    return default


def _merge_default_agent_tool_permissions(
    items: list[AgentToolPermissionItem],
) -> list[AgentToolPermissionItem]:
    default_items = {
        item["tool_name"]: item["mode"] for item in get_default_agent_tool_permissions()
    }
    configured_items = {item.tool_name: item.mode for item in items}

    merged_items = []
    for tool_name, default_mode in default_items.items():
        merged_items.append(
            AgentToolPermissionItem(
                tool_name=tool_name,
                mode=configured_items.get(tool_name, default_mode),
            )
        )
    return merged_items


def _parse_index_enabled_projects(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, str) and item]


def _normalize_index_mode(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    return value if value in _VALID_INDEX_MODES else DEFAULT_INDEX_MODE


def _normalize_index_auto_strategy(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    return value if value in _VALID_INDEX_AUTO_STRATEGIES else DEFAULT_INDEX_AUTO_STRATEGY


def _parse_int_setting(raw_value: str | None, *, default: int) -> int:
    if raw_value is None or raw_value == "":
        return default
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


@router.get(
    "",
    response_model=SettingsResponse,
    summary="获取设置",
)
async def get_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SettingsResponse:
    """
    获取所有用户设置。

    Args:
        session: 数据库 session。

    Returns:
        当前设置。
    """
    settings_list = await setting_repo.get_all(session)

    # 将设置列表转换为字典
    settings_dict = {s.key: s.value for s in settings_list}
    agent_tool_permissions = _merge_default_agent_tool_permissions(
        _parse_agent_tool_permissions(
            settings_dict.get(
                SETTING_KEY_AGENT_TOOL_PERMISSIONS,
                DEFAULT_SETTINGS[SETTING_KEY_AGENT_TOOL_PERMISSIONS],
            )
        )
    )

    return SettingsResponse(
        language=settings_dict.get(SETTING_KEY_LANGUAGE, DEFAULT_SETTINGS[SETTING_KEY_LANGUAGE]),
        theme=settings_dict.get(SETTING_KEY_THEME, DEFAULT_SETTINGS[SETTING_KEY_THEME]),
        font_family=settings_dict.get(
            SETTING_KEY_FONT_FAMILY, DEFAULT_SETTINGS[SETTING_KEY_FONT_FAMILY]
        ),
        code_font_family=settings_dict.get(
            SETTING_KEY_CODE_FONT_FAMILY, DEFAULT_SETTINGS[SETTING_KEY_CODE_FONT_FAMILY]
        ),
        default_model=settings_dict.get(
            SETTING_KEY_DEFAULT_MODEL, DEFAULT_SETTINGS[SETTING_KEY_DEFAULT_MODEL]
        ),
        light_model=settings_dict.get(
            SETTING_KEY_LIGHT_MODEL, DEFAULT_SETTINGS[SETTING_KEY_LIGHT_MODEL]
        ),
        default_embedding_model=settings_dict.get(
            SETTING_KEY_DEFAULT_EMBEDDING_MODEL,
            DEFAULT_SETTINGS[SETTING_KEY_DEFAULT_EMBEDDING_MODEL],
        ),
        index_mode=_normalize_index_mode(
            settings_dict.get(
                SETTING_KEY_INDEX_MODE,
                DEFAULT_SETTINGS[SETTING_KEY_INDEX_MODE],
            )
        ),
        index_enabled_projects=_parse_index_enabled_projects(
            settings_dict.get(SETTING_KEY_INDEX_ENABLED_PROJECTS)
        ),
        index_chunk_size=_parse_int_setting(
            settings_dict.get(
                SETTING_KEY_INDEX_CHUNK_SIZE,
                DEFAULT_SETTINGS[SETTING_KEY_INDEX_CHUNK_SIZE],
            ),
            default=DEFAULT_INDEX_CHUNK_SIZE,
        ),
        index_chunk_overlap=_parse_int_setting(
            settings_dict.get(
                SETTING_KEY_INDEX_CHUNK_OVERLAP,
                DEFAULT_SETTINGS[SETTING_KEY_INDEX_CHUNK_OVERLAP],
            ),
            default=DEFAULT_INDEX_CHUNK_OVERLAP,
        ),
        index_auto_strategy=_normalize_index_auto_strategy(
            settings_dict.get(
                SETTING_KEY_INDEX_AUTO_STRATEGY,
                DEFAULT_SETTINGS[SETTING_KEY_INDEX_AUTO_STRATEGY],
            )
        ),
        index_rerank_enabled=_parse_bool_setting(
            settings_dict.get(
                SETTING_KEY_INDEX_RERANK_ENABLED,
                DEFAULT_SETTINGS[SETTING_KEY_INDEX_RERANK_ENABLED],
            ),
            default=DEFAULT_INDEX_RERANK_ENABLED,
        ),
        default_rerank_model=settings_dict.get(
            SETTING_KEY_DEFAULT_RERANK_MODEL,
            DEFAULT_SETTINGS[SETTING_KEY_DEFAULT_RERANK_MODEL],
        ),
        agent_bypass_tool_approval=_parse_bool_setting(
            settings_dict.get(
                SETTING_KEY_AGENT_BYPASS_TOOL_APPROVAL,
                DEFAULT_SETTINGS[SETTING_KEY_AGENT_BYPASS_TOOL_APPROVAL],
            ),
            default=False,
        ),
        agent_tool_permissions=agent_tool_permissions,
        audit_persist_details=_parse_bool_setting(
            settings_dict.get(
                SETTING_KEY_AUDIT_PERSIST_DETAILS,
                DEFAULT_SETTINGS[SETTING_KEY_AUDIT_PERSIST_DETAILS],
            ),
            default=False,
        ),
    )


@router.put(
    "",
    response_model=SettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="更新设置",
)
@router.patch(
    "",
    response_model=SettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="更新设置",
)
async def update_settings(
    request: SettingsUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SettingsResponse:
    """
    批量更新用户设置。

    Args:
        request: 设置更新请求，只更新非 None 的字段。
        session: 数据库 session。

    Returns:
        更新后的设置。
    """
    is_restricted_update = any(
        value is not None
        for value in (
            request.default_model,
            request.light_model,
            request.default_embedding_model,
            request.index_mode,
            request.index_enabled_projects,
            request.index_chunk_size,
            request.index_chunk_overlap,
            request.index_auto_strategy,
            request.index_rerank_enabled,
            request.default_rerank_model,
        )
    )
    if is_restricted_update:
        await require_agent_settings_unlocked(session)

    logger.info(f"更新设置: {request}")

    settings_list = await setting_repo.get_all(session)
    current_settings = {setting.key: setting.value for setting in settings_list}

    # 构建要更新的设置字典
    settings_to_update: dict[str, str] = {}
    index_config_changed = False
    index_contract_changed = False
    next_audit_details_persistence: bool | None = None

    if request.language is not None:
        settings_to_update[SETTING_KEY_LANGUAGE] = request.language
    if request.theme is not None:
        settings_to_update[SETTING_KEY_THEME] = request.theme
    if request.font_family is not None:
        settings_to_update[SETTING_KEY_FONT_FAMILY] = request.font_family
    if request.code_font_family is not None:
        settings_to_update[SETTING_KEY_CODE_FONT_FAMILY] = request.code_font_family
    if request.default_model is not None:
        settings_to_update[SETTING_KEY_DEFAULT_MODEL] = request.default_model
    if request.light_model is not None:
        settings_to_update[SETTING_KEY_LIGHT_MODEL] = request.light_model
    if request.default_embedding_model is not None:
        old_embedding_model = current_settings.get(
            SETTING_KEY_DEFAULT_EMBEDDING_MODEL,
            DEFAULT_SETTINGS[SETTING_KEY_DEFAULT_EMBEDDING_MODEL],
        )
        if old_embedding_model and old_embedding_model != request.default_embedding_model:
            index_contract_changed = True
        settings_to_update[SETTING_KEY_DEFAULT_EMBEDDING_MODEL] = (
            request.default_embedding_model
        )
        index_config_changed = True
    if request.index_mode is not None:
        new_mode = _normalize_index_mode(request.index_mode)
        old_mode = _normalize_index_mode(
            current_settings.get(
                SETTING_KEY_INDEX_MODE,
                DEFAULT_SETTINGS[SETTING_KEY_INDEX_MODE],
            )
        )
        if new_mode != old_mode:
            index_config_changed = True
        settings_to_update[SETTING_KEY_INDEX_MODE] = new_mode
    if request.index_enabled_projects is not None:
        settings_to_update[SETTING_KEY_INDEX_ENABLED_PROJECTS] = json.dumps(
            request.index_enabled_projects,
            ensure_ascii=False,
        )
        index_config_changed = True
    if request.index_chunk_size is not None:
        old_chunk_size = _parse_int_setting(
            current_settings.get(SETTING_KEY_INDEX_CHUNK_SIZE),
            default=DEFAULT_INDEX_CHUNK_SIZE,
        )
        new_chunk_size = max(1, request.index_chunk_size)
        if new_chunk_size != old_chunk_size:
            index_contract_changed = True
            index_config_changed = True
        settings_to_update[SETTING_KEY_INDEX_CHUNK_SIZE] = str(new_chunk_size)
    if request.index_chunk_overlap is not None:
        old_chunk_overlap = _parse_int_setting(
            current_settings.get(SETTING_KEY_INDEX_CHUNK_OVERLAP),
            default=DEFAULT_INDEX_CHUNK_OVERLAP,
        )
        new_chunk_overlap = max(0, request.index_chunk_overlap)
        if new_chunk_overlap != old_chunk_overlap:
            index_contract_changed = True
            index_config_changed = True
        settings_to_update[SETTING_KEY_INDEX_CHUNK_OVERLAP] = str(new_chunk_overlap)
    if request.index_auto_strategy is not None:
        new_strategy = _normalize_index_auto_strategy(request.index_auto_strategy)
        old_strategy = _normalize_index_auto_strategy(
            current_settings.get(
                SETTING_KEY_INDEX_AUTO_STRATEGY,
                DEFAULT_SETTINGS[SETTING_KEY_INDEX_AUTO_STRATEGY],
            )
        )
        if new_strategy != old_strategy:
            index_config_changed = True
        settings_to_update[SETTING_KEY_INDEX_AUTO_STRATEGY] = new_strategy
    if request.index_rerank_enabled is not None:
        settings_to_update[SETTING_KEY_INDEX_RERANK_ENABLED] = json.dumps(
            request.index_rerank_enabled, ensure_ascii=False
        )
        index_config_changed = True
    if request.default_rerank_model is not None:
        settings_to_update[SETTING_KEY_DEFAULT_RERANK_MODEL] = (
            request.default_rerank_model
        )
        index_config_changed = True
    if request.agent_bypass_tool_approval is not None:
        settings_to_update[SETTING_KEY_AGENT_BYPASS_TOOL_APPROVAL] = json.dumps(
            request.agent_bypass_tool_approval,
            ensure_ascii=False,
        )
    if request.agent_tool_permissions is not None:
        settings_to_update[SETTING_KEY_AGENT_TOOL_PERMISSIONS] = json.dumps(
            [item.model_dump(mode="json") for item in request.agent_tool_permissions],
            ensure_ascii=False,
        )
    if request.audit_persist_details is not None:
        settings_to_update[SETTING_KEY_AUDIT_PERSIST_DETAILS] = json.dumps(
            request.audit_persist_details,
            ensure_ascii=False,
        )
        next_audit_details_persistence = request.audit_persist_details

    # 分块参数或嵌入模型变更会使现有索引失效，需要标记重建。
    if index_contract_changed:
        await retrieval_chapter_index_state_repo.mark_all_needs_rebuild(session)
        await retrieval_index_repo.mark_all_needs_rebuild(session)

    # 批量更新
    if settings_to_update:
        await setting_repo.bulk_upsert(session, settings_to_update)
    if next_audit_details_persistence is not None:
        set_audit_details_persistence(next_audit_details_persistence)

    # 索引配置变更后通知前端刷新索引状态。
    if index_config_changed:
        schedule_emit_index_config(session)

    # 返回更新后的完整设置
    return await get_settings(session)


@router.get(
    "/audit-details/storage",
    response_model=AuditDetailsStorageResponse,
    summary="获取 LLM 调用详情存储概览",
)
async def get_audit_details_storage(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuditDetailsStorageResponse:
    storage = await LLMAuditLogRepo(session).get_details_storage()
    return AuditDetailsStorageResponse(
        detail_records_count=storage.detail_records_count,
        detail_bytes=storage.detail_bytes,
    )


@router.delete(
    "/audit-details",
    response_model=ClearAuditDetailsResponse,
    summary="清空 LLM 调用详情",
)
async def clear_audit_details(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClearAuditDetailsResponse:
    cleared = await LLMAuditLogRepo(session).clear_details()
    return ClearAuditDetailsResponse(
        cleared_records_count=cleared.cleared_records_count,
        cleared_detail_bytes=cleared.cleared_detail_bytes,
    )
