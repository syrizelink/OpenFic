# -*- coding: utf-8 -*-
"""
Prompt Chain Compiler - 提示词链编译器。

负责编译 prompt chain，将宏替换为实际值。
"""

from dataclasses import dataclass
from xml.sax.saxutils import escape

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.macro.evaluator import MacroEvaluator
from app.macro.types import ChapterContext, MacroContext, WorldContext
from app.storage.models.world_info_entry import WorldInfoEntry


@dataclass
class CompiledEntry:
    """
    编译后的条目。

    Attributes:
        role: 角色类型。
        content: 编译后的内容。
        token_count: Token 计数（编译后）。
    """

    role: str
    content: str
    token_count: int


@dataclass
class CompileResult:
    """
    编译结果。

    Attributes:
        entries: 编译后的条目列表。
        total_tokens: 总 Token 数。
    """

    entries: list[CompiledEntry]
    total_tokens: int


@dataclass
class EntryInput:
    """
    编译输入条目。

    Attributes:
        role: 角色类型。
        content: 原始内容（含宏）。
        order_index: 排序索引。
        is_enabled: 是否启用。
    """

    role: str
    content: str
    order_index: int
    is_enabled: bool


class PromptChainCompiler:
    """提示词链编译器。"""

    def __init__(self, session: AsyncSession):
        """
        初始化编译器。

        Args:
            session: 数据库 session。
        """
        self.session = session

    async def compile(
        self,
        entries: list[EntryInput],
        project_id: str | None = None,
        chapter_id: str | None = None,
        agent_session_id: str | None = None,
    ) -> CompileResult:
        """
        编译提示词链。

        Args:
            entries: 条目列表（按 order_index 排序）。
            project_id: 项目 ID（用于 getmem）。
            chapter_id: 当前章节 ID（用于 getmem）。
            agent_session_id: Agent会话ID。

        Returns:
            编译结果。
        """
        chapter_context = None
        if project_id and chapter_id is not None:
            chapter_context = await self._load_chapter_context(
                project_id, chapter_id
            )

        world_context = None
        if project_id:
            world_context = await self._load_world_context(project_id)

        context = MacroContext(
            variables={},
            chapter_context=chapter_context,
            world_context=world_context,
        )

        evaluator = MacroEvaluator(context)

        sorted_entries = sorted(entries, key=lambda e: e.order_index)
        enabled_entries = [e for e in sorted_entries if e.is_enabled]

        compiled_entries: list[CompiledEntry] = []
        total_tokens = 0

        for entry in enabled_entries:
            try:
                compiled_content = evaluator.evaluate_text(entry.content)
            except Exception as e:
                logger.warning(f"编译条目失败: {e}，使用原始内容")
                compiled_content = entry.content

            token_count = self._estimate_tokens(compiled_content)
            total_tokens += token_count

            compiled_entries.append(
                CompiledEntry(
                    role=entry.role,
                    content=compiled_content,
                    token_count=token_count,
                )
            )

        return CompileResult(
            entries=compiled_entries,
            total_tokens=total_tokens,
        )

    async def _load_chapter_context(
        self, project_id: str, chapter_id: str
    ) -> ChapterContext:
        """加载章节上下文。"""
        from app.memory.chapter import build_context

        try:
            built = await build_context(self.session, project_id, chapter_id)

            return ChapterContext(
                project_id=project_id,
                chapter_id=chapter_id,
                latest_field=built.latest_field.content,
                near_field=built.near_field.content,
                mid_field=built.mid_field.content,
                far_field=built.far_field.content,
                chapter_list_field=built.chapter_list_field.content,
            )
        except Exception as e:
            logger.warning(f"加载章节上下文失败: {e}")
            return ChapterContext(
                project_id=project_id,
                chapter_id=chapter_id,
            )
        except Exception as e:
            logger.warning(f"加载章节上下文失败: {e}")
            return ChapterContext(
                project_id=project_id,
                chapter_id=chapter_id,
            )

    async def _load_world_context(self, project_id: str) -> WorldContext:
        """加载世界书上下文。"""
        try:
            from app.storage.repos import (
                world_info_entry_repo,
                world_info_repo,
            )

            world_info = await world_info_repo.get_by_project_id(
                self.session, project_id
            )
            if world_info is None:
                return WorldContext()

            entries = await world_info_entry_repo.list_enabled_by_world_info(
                self.session,
                world_info.id,
            )
            entries.sort(key=lambda entry: entry.order)
            return WorldContext(content=self._format_world_entries(entries))
        except Exception as e:
            logger.warning(f"加载世界书上下文失败: {e}")
            return WorldContext()

    def _format_world_entries(self, entries: list[WorldInfoEntry]) -> str:
        """按 XML 格式输出世界书条目。"""
        return "\n".join(
            f"<{self._xml_tag_name(entry.name)}>\n{escape(entry.content)}\n</{self._xml_tag_name(entry.name)}>"
            for entry in entries
        )

    def _xml_tag_name(self, name: str) -> str:
        """将条目名转换为 XML 标签名。"""
        return name.strip() or "entry"

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数量。"""
        return len(text) // 2
