import json
from typing import cast

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.runnables import RunnableConfig

from app.agent_runtime.tools.base import HookContext, HookResult
from app.agent_runtime.tools.permission_metadata import (
    SETTING_KEY_AGENT_BYPASS_TOOL_APPROVAL,
    SETTING_KEY_AGENT_TOOL_PERMISSIONS,
    get_default_tool_permission_mode,
)
from app.storage.repos import setting_repo


def _extract_db_session(config: RunnableConfig | None) -> AsyncSession | None:
    if not isinstance(config, dict):
        return None
    configurable = config.get("configurable") or {}
    if not isinstance(configurable, dict):
        return None
    return cast(AsyncSession | None, configurable.get("db_session"))


async def _read_user_permissions(session: AsyncSession) -> dict[str, str]:
    try:
        setting = await setting_repo.get_by_key(session, SETTING_KEY_AGENT_TOOL_PERMISSIONS)
        if setting is None or not setting.value:
            return {}
        payload = json.loads(setting.value)
        if not isinstance(payload, list):
            return {}
        return {
            str(item["tool_name"]): str(item["mode"])
            for item in payload
            if isinstance(item, dict) and "tool_name" in item and "mode" in item
        }
    except Exception:
        logger.warning("读取 agent_tool_permissions 失败，回退到默认权限")
        return {}


async def _read_bypass_tool_approval(session: AsyncSession) -> bool:
    try:
        setting = await setting_repo.get_by_key(session, SETTING_KEY_AGENT_BYPASS_TOOL_APPROVAL)
        if setting is None or not setting.value:
            return False
        payload = json.loads(setting.value)
        if isinstance(payload, bool):
            return payload
        if isinstance(payload, (int, float)):
            return bool(payload)
        return False
    except Exception:
        logger.warning("读取 agent_bypass_tool_approval 失败，回退到默认值")
        return False


def _approval_interrupt_payload(
    context: HookContext,
    *,
    denied: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "tool_approval",
        "tool_name": context.tool_name,
        "args": context.args,
    }
    if denied:
        payload["denied"] = True
    return payload


async def auth_hook(context: HookContext) -> HookResult:
    session = _extract_db_session(context.config)
    if session is not None and await _read_bypass_tool_approval(session):
        return HookResult(proceed=True)
    user_permissions = await _read_user_permissions(session) if session is not None else {}

    mode = user_permissions.get(context.tool_name)
    if mode is None:
        mode = get_default_tool_permission_mode(context.tool_name)

    if mode == "deny":
        return HookResult(
            proceed=False,
            interrupt_payload=_approval_interrupt_payload(context, denied=True),
        )

    if mode == "allow":
        return HookResult(proceed=True)

    if mode == "ask":
        return HookResult(
            proceed=False,
            interrupt_payload=_approval_interrupt_payload(context),
        )

    if context.access_level == "readonly":
        return HookResult(proceed=True)

    return HookResult(
        proceed=False,
        interrupt_payload=_approval_interrupt_payload(context),
    )
