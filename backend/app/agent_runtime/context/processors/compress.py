"""System prompt compression processor for context building."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Any, TypeVar, cast

from langchain_core.messages import BaseMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.types import ContextMessage
from app.storage.repos import setting_repo

SETTING_KEY_COMPRESS_SYSTEM_PROMPTS = "compress_system_prompts"

_SYSTEM_JOIN_SEPARATOR = "\n\n"

TMessage = TypeVar("TMessage", bound=BaseMessage)


async def compress_system_prompts_if_enabled(
    messages: list[ContextMessage],
    db_session: AsyncSession,
) -> list[ContextMessage]:
    """设置开启时将连续的 system 消息合并为一条，否则原样返回。"""
    if not await is_compress_system_prompts_enabled(db_session):
        return messages
    return compress_system_prompts(messages)


async def is_compress_system_prompts_enabled(db_session: AsyncSession) -> bool:
    """读取并解析压缩系统提示词开关。"""
    try:
        row = await setting_repo.get_by_key(
            db_session,
            SETTING_KEY_COMPRESS_SYSTEM_PROMPTS,
        )
    except Exception as e:
        raise ContextBuildError(
            "settings",
            "failed to load compress_system_prompts setting",
            cause=e,
        ) from e
    if row is None or row.value == "":
        return False
    return row.value.strip().lower() not in {"false", "0", "no", "off"}


def compress_system_prompts(messages: list[ContextMessage]) -> list[ContextMessage]:
    """将连续的 system 消息合并为一条，非连续 system 消息保持原样。"""
    out: list[ContextMessage] = []
    for message in messages:
        if message.role == "system" and out and out[-1].role == "system":
            previous = out[-1]
            out[-1] = replace(
                previous,
                content=f"{previous.content}{_SYSTEM_JOIN_SEPARATOR}{message.content}",
            )
        else:
            out.append(message)
    return out


def merge_consecutive_system_dicts(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """将 role/content 字典列表中连续的 system 消息合并为一条。"""
    out: list[dict[str, Any]] = []
    for message in messages:
        if (
            message.get("role") == "system"
            and out
            and out[-1].get("role") == "system"
        ):
            previous = out[-1]
            out[-1] = {
                **previous,
                "content": (
                    f"{previous.get('content', '')}"
                    f"{_SYSTEM_JOIN_SEPARATOR}{message.get('content', '')}"
                ),
            }
        else:
            out.append(message)
    return out


def merge_consecutive_system_messages(
    messages: Sequence[TMessage],
) -> list[TMessage]:
    """将 LangChain 消息列表中连续的 system 消息合并为一条。"""
    out: list[TMessage] = []
    for message in messages:
        if out and isinstance(out[-1], SystemMessage) and isinstance(message, SystemMessage):
            out[-1] = cast(
                TMessage,
                SystemMessage(
                    content=f"{out[-1].content}{_SYSTEM_JOIN_SEPARATOR}{message.content}"
                ),
            )
        else:
            out.append(message)
    return out
