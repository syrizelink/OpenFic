/* eslint-disable react-refresh/only-export-components */
import type { ReactNode } from "react";
import {
  BookOpen,
  Bot,
  BotMessageSquare,
  BotOff,
  FilePenLine,
  FileSearch,
  FileText,
  ListOrdered,
  MessageSquareWarning,
  Puzzle,
  Trash2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { AgentMessage } from "@/lib/agent.types";
import { formatChapterDisplayName } from "@/features/assistant/lib/chapter-tool-preview";
import {
  getExploreToolNames as getCatalogExploreToolNames,
  REGISTERED_TOOL_NAMES,
  isExploreToolName,
  type RegisteredToolName,
  type ToolContentMode,
  type ToolGroup,
} from "./tool-message-catalog";

import { AskUserToolMessage } from "../ask-user/ask-user-tool-message";
import {
  ChapterToolMessage,
} from "../chapter/chapter-tool-message";
import {
  EditNoteToolMessage,
  WriteNoteToolMessage,
} from "../note/note-tool-message";
import {
  getSubagentDispatchDetail,
  getSubagentDispatchTitle,
} from "../orchestration/dispatch-subagent-tool-message";
import { DispatchSubagentToolMessageBody } from "../orchestration/dispatch-subagent-tool-message-body";
import { NotifySubagentToolMessage } from "../orchestration/notify-subagent-tool-message";
import {
  getNotifySubagentDetail,
  getNotifySubagentTitle,
} from "../orchestration/notify-subagent-tool-message-utils";
import { PlanToolMessage } from "../plan/plan-tool-message";
import {
  getRecycleSubagentDetail,
  getRecycleSubagentTitle,
} from "../orchestration/recycle-subagent-tool-message";
import { SkillToolMessage } from "../skill/skill-tool-message";
import {
  CreateVolumeToolMessage,
  DeleteVolumeToolMessage,
  EditVolumeToolMessage,
  MoveChapterToVolumeToolMessage,
} from "../volume/volume-tool-message";
import { getPlanToolDisplayConfig } from "../plan/plan-tool-message.utils";
import {
  asString,
  formatCategoryRefLabel,
  formatChapterRefLabel,
  formatChapterSummaryQuery,
  formatNoteRefLabel,
  formatRangeSummaryQuery,
  formatVolumeRefLabel,
  getAskUserQuestionCountDetail,
  getAskUserTitle,
  getChapterList,
  getChapterPayload,
  getChapterSummaryList,
  getNoteItemList,
  getNotePayload,
  getPlanCountDetail,
  getPlanTopicDetail,
  getRangeSummaryList,
  getReadChapterDetail,
  getStreamingData,
  getToolRef,
  getToolResultData,
  getVolumeList,
  getVolumePayload,
  getWorldInfoContent,
  isRecord,
  parseWorldInfoEntries,
} from "./tool-message-utils";

export { REGISTERED_TOOL_NAMES };

export interface ToolDescriptor {
  toolName: RegisteredToolName;
  group: ToolGroup;
  tag: string;
  isExplore: boolean;
  contentMode: ToolContentMode;
  icon: LucideIcon;
  getTitle: (message: AgentMessage) => string;
  getDetail?: (message: AgentMessage) => string | undefined;
  defaultExpanded?: (message: AgentMessage) => boolean;
  render?: (message: AgentMessage) => ReactNode;
}

function getPlanDetailForDisplayKind(
  message: AgentMessage,
  detailKind: ReturnType<typeof getPlanToolDisplayConfig>["detailKind"]
): string | undefined {
  return detailKind === "count" ? getPlanCountDetail(message) : getPlanTopicDetail(message);
}

const TOOL_REGISTRY = {
  dispatch_subagent: {
    toolName: "dispatch_subagent",
    group: "orchestration",
    tag: "dispatch",
    isExplore: false,
    contentMode: "expandable",
    icon: Bot,
    getTitle: (message) => getSubagentDispatchTitle(message),
    getDetail: (message) => getSubagentDispatchDetail(message),
    render: (message) => <DispatchSubagentToolMessageBody message={message} />,
  },
  notify_subagent: {
    toolName: "notify_subagent",
    group: "orchestration",
    tag: "notify",
    isExplore: false,
    contentMode: "expandable",
    icon: BotMessageSquare,
    getTitle: () => getNotifySubagentTitle(),
    getDetail: (message) => getNotifySubagentDetail(message),
    render: (message) => <NotifySubagentToolMessage message={message} />,
  },
  recycle_subagent: {
    toolName: "recycle_subagent",
    group: "orchestration",
    tag: "recycle",
    isExplore: false,
    contentMode: "hidden",
    icon: BotOff,
    getTitle: () => getRecycleSubagentTitle(),
    getDetail: (message) => getRecycleSubagentDetail(message),
  },
  ask_user: {
    toolName: "ask_user",
    group: "interaction",
    tag: "clarification",
    isExplore: false,
    contentMode: "expandable",
    icon: MessageSquareWarning,
    getTitle: (message) => getAskUserTitle(message),
    getDetail: (message) => getAskUserQuestionCountDetail(message),
    render: (message) => <AskUserToolMessage message={message} />,
  },
  read_chapter: {
    toolName: "read_chapter",
    group: "chapter",
    tag: "read",
    isExplore: true,
    contentMode: "hidden",
    icon: BookOpen,
    getTitle: () => "读取章节",
    getDetail: (message) => getReadChapterDetail(message),
  },
  write_chapter: {
    toolName: "write_chapter",
    group: "chapter",
    tag: "write",
    isExplore: false,
    contentMode: "expandable",
    icon: FilePenLine,
    getTitle: () => "写入章节",
    getDetail: (message) => getChapterPayload(message).title,
    defaultExpanded: () => true,
    render: (message) => <ChapterToolMessage message={message} />,
  },
  edit_chapter: {
    toolName: "edit_chapter",
    group: "chapter",
    tag: "edit",
    isExplore: false,
    contentMode: "expandable",
    icon: FilePenLine,
    getTitle: () => "编辑章节",
    getDetail: (message) =>
      getChapterPayload(message).title ?? formatChapterRefLabel(getToolRef(message, "chapter_ref")),
    defaultExpanded: () => true,
    render: (message) => <ChapterToolMessage message={message} />,
  },
  delete_chapter: {
    toolName: "delete_chapter",
    group: "chapter",
    tag: "delete",
    isExplore: false,
    contentMode: "hidden",
    icon: Trash2,
    getTitle: () => "删除章节",
    getDetail: (message) => {
      const chapter = getChapterPayload(message);
      return (
        formatChapterDisplayName({
          order: chapter.order,
          title: chapter.title,
          chapterId: chapter.chapter_id,
        }) ?? formatChapterRefLabel(getToolRef(message, "chapter_ref"))
      );
    },
  },
  list_notes: {
    toolName: "list_notes",
    group: "note",
    tag: "list",
    isExplore: true,
    contentMode: "hidden",
    icon: ListOrdered,
    getTitle: () => "笔记列表",
    getDetail: (message) => {
      const items = getNoteItemList(message);
      return items.length > 0 ? `${items.length} 项` : undefined;
    },
  },
  read_note: {
    toolName: "read_note",
    group: "note",
    tag: "read",
    isExplore: true,
    contentMode: "hidden",
    icon: BookOpen,
    getTitle: () => "读取笔记",
    getDetail: (message) =>
      getNotePayload(message).title ?? formatNoteRefLabel(getToolRef(message, "note_ref")),
  },
  write_note: {
    toolName: "write_note",
    group: "note",
    tag: "write",
    isExplore: false,
    contentMode: "expandable",
    icon: FilePenLine,
    getTitle: () => "写入笔记",
    getDetail: (message) => getNotePayload(message).title,
    defaultExpanded: () => true,
    render: (message) => <WriteNoteToolMessage message={message} />,
  },
  edit_note: {
    toolName: "edit_note",
    group: "note",
    tag: "edit",
    isExplore: false,
    contentMode: "expandable",
    icon: FilePenLine,
    getTitle: () => "编辑笔记",
    getDetail: (message) =>
      getNotePayload(message).title ?? formatNoteRefLabel(getToolRef(message, "note_ref")),
    defaultExpanded: () => true,
    render: (message) => <EditNoteToolMessage message={message} />,
  },
  delete_note: {
    toolName: "delete_note",
    group: "note",
    tag: "delete",
    isExplore: false,
    contentMode: "hidden",
    icon: Trash2,
    getTitle: () => "删除笔记",
    getDetail: (message) =>
      getNotePayload(message).title ?? formatNoteRefLabel(getToolRef(message, "note_ref")),
  },
  move_note: {
    toolName: "move_note",
    group: "note",
    tag: "move",
    isExplore: false,
    contentMode: "hidden",
    icon: FilePenLine,
    getTitle: () => "移动笔记",
    getDetail: (message) => {
      const note = getNotePayload(message);
      const noteLabel = note.title ?? formatNoteRefLabel(getToolRef(message, "note_ref"));
      const data = message.toolResult?.data;
      const target = isRecord(data) && isRecord(data.target_category) ? data.target_category : null;
      const targetLabel = asString(target?.title) ?? formatCategoryRefLabel(getToolRef(message, "target_category_ref")) ?? "根层级";
      if (!noteLabel) return undefined;
      return `${noteLabel} \u2192 ${targetLabel}`;
    },
  },
  create_note_category: {
    toolName: "create_note_category",
    group: "note",
    tag: "write",
    isExplore: false,
    contentMode: "hidden",
    icon: FilePenLine,
    getTitle: () => "创建分类",
    getDetail: (message) => {
      const data = getToolResultData(message);
      if (isRecord(data) && isRecord(data.category)) {
        return asString(data.category.title);
      }
      return asString(getStreamingData(message).title);
    },
  },
  list_chapters: {
    toolName: "list_chapters",
    group: "chapter",
    tag: "list",
    isExplore: true,
    contentMode: "hidden",
    icon: ListOrdered,
    getTitle: () => "章节列表",
    getDetail: (message) => {
      const chapters = getChapterList(message);
      return chapters.length > 0 ? `${chapters.length} 个章节` : undefined;
    },
  },
  search_chapters: {
    toolName: "search_chapters",
    group: "chapter",
    tag: "search",
    isExplore: true,
    contentMode: "hidden",
    icon: FileSearch,
    getTitle: () => "章节搜索",
    getDetail: (message) => {
      const data = getToolResultData(message);
      if (!isRecord(data)) return undefined;
      const results = Array.isArray(data.results) ? data.results : [];
      if (results.length === 0) return undefined;
      const query = typeof data.query === "string" && data.query ? data.query : undefined;
      return query ? `${query} · ${results.length} 个匹配` : `${results.length} 个匹配章节`;
    },
  },
  list_volumes: {
    toolName: "list_volumes",
    group: "volume",
    tag: "list",
    isExplore: true,
    contentMode: "hidden",
    icon: ListOrdered,
    getTitle: () => "卷列表",
    getDetail: (message) => {
      const volumes = getVolumeList(message);
      return volumes.length > 0 ? `${volumes.length} 个卷` : undefined;
    },
  },
  create_volume: {
    toolName: "create_volume",
    group: "volume",
    tag: "create",
    isExplore: false,
    contentMode: "static",
    icon: FileText,
    getTitle: () => "创建卷",
    getDetail: (message) =>
      getVolumePayload(message)?.title ?? asString(getStreamingData(message).title),
    render: (message) => <CreateVolumeToolMessage message={message} />,
  },
  edit_volume: {
    toolName: "edit_volume",
    group: "volume",
    tag: "edit",
    isExplore: false,
    contentMode: "static",
    icon: FilePenLine,
    getTitle: () => "编辑卷",
    getDetail: (message) =>
      getVolumePayload(message)?.title ??
      asString(getStreamingData(message).new_title) ??
      formatVolumeRefLabel(getToolRef(message, "volume_ref")),
    render: (message) => <EditVolumeToolMessage message={message} />,
  },
  delete_volume: {
    toolName: "delete_volume",
    group: "volume",
    tag: "delete",
    isExplore: false,
    contentMode: "static",
    icon: Trash2,
    getTitle: () => "删除卷",
    getDetail: (message) => formatVolumeRefLabel(getToolRef(message, "volume_ref")),
    render: (message) => <DeleteVolumeToolMessage message={message} />,
  },
  move_chapter_to_volume: {
    toolName: "move_chapter_to_volume",
    group: "volume",
    tag: "move",
    isExplore: false,
    contentMode: "static",
    icon: FilePenLine,
    getTitle: () => "移动章节到卷",
    getDetail: (message) =>
      getChapterPayload(message).title ?? formatChapterRefLabel(getToolRef(message, "chapter_ref")),
    render: (message) => <MoveChapterToVolumeToolMessage message={message} />,
  },
  read_chapter_summaries: {
    toolName: "read_chapter_summaries",
    group: "context",
    tag: "chapter-summary",
    isExplore: true,
    contentMode: "hidden",
    icon: FileSearch,
    getTitle: () => "章节摘要",
    getDetail: (message) => {
      const summaries = getChapterSummaryList(message);
      return summaries.length > 0
        ? `${summaries.length} 条摘要`
        : formatChapterSummaryQuery(message);
    },
  },
  read_range_summaries: {
    toolName: "read_range_summaries",
    group: "context",
    tag: "range-summary",
    isExplore: true,
    contentMode: "hidden",
    icon: FileText,
    getTitle: () => "区间摘要",
    getDetail: (message) => {
      const summaries = getRangeSummaryList(message);
      return summaries.length > 0
        ? `${summaries.length} 条摘要`
        : formatRangeSummaryQuery(message);
    },
  },
  read_world_info: {
    toolName: "read_world_info",
    group: "context",
    tag: "world-info",
    isExplore: true,
    contentMode: "hidden",
    icon: BookOpen,
    getTitle: () => "世界书",
    getDetail: (message) => {
      const content = getWorldInfoContent(message);
      const entries = parseWorldInfoEntries(content);
      if (entries.length > 0) return `${entries.length} 条条目`;
      return content ? "已匹配内容" : undefined;
    },
  },
  create_plan: {
    toolName: "create_plan",
    group: "plan",
    tag: "create",
    isExplore: false,
    contentMode: getPlanToolDisplayConfig("create_plan").contentMode,
    icon: ListOrdered,
    getTitle: () => "创建计划",
    getDetail: (message) =>
      getPlanDetailForDisplayKind(message, getPlanToolDisplayConfig("create_plan").detailKind),
    defaultExpanded: () => getPlanToolDisplayConfig("create_plan").defaultExpanded,
    render: (message) => <PlanToolMessage message={message} />,
  },
  update_plan: {
    toolName: "update_plan",
    group: "plan",
    tag: "update",
    isExplore: false,
    contentMode: getPlanToolDisplayConfig("update_plan").contentMode,
    icon: ListOrdered,
    getTitle: () => "更新计划",
    getDetail: (message) =>
      getPlanDetailForDisplayKind(message, getPlanToolDisplayConfig("update_plan").detailKind),
    defaultExpanded: () => getPlanToolDisplayConfig("update_plan").defaultExpanded,
    render: (message) => <PlanToolMessage message={message} />,
  },
  get_plan: {
    toolName: "get_plan",
    group: "plan",
    tag: "read",
    isExplore: false,
    contentMode: getPlanToolDisplayConfig("get_plan").contentMode,
    icon: ListOrdered,
    getTitle: () => "读取计划",
    getDetail: (message) =>
      getPlanDetailForDisplayKind(message, getPlanToolDisplayConfig("get_plan").detailKind),
    render: (message) => <PlanToolMessage message={message} />,
  },
  list_plan: {
    toolName: "list_plan",
    group: "plan",
    tag: "list",
    isExplore: false,
    contentMode: getPlanToolDisplayConfig("list_plan").contentMode,
    icon: ListOrdered,
    getTitle: () => "计划列表",
    getDetail: (message) =>
      getPlanDetailForDisplayKind(message, getPlanToolDisplayConfig("list_plan").detailKind),
    render: (message) => <PlanToolMessage message={message} />,
  },
  use_skill: {
    toolName: "use_skill",
    group: "skill",
    tag: "install",
    isExplore: false,
    contentMode: "static",
    icon: Puzzle,
    getTitle: () => "装载技能",
    getDetail: (message) => {
      const data = getStreamingData(message);
      return asString(data.name) ?? asString(data.skill_id);
    },
    render: (message) => (
      <SkillToolMessage
        message={message}
        actionLabel="装载技能"
        emptyTitle="未返回技能装载信息"
      />
    ),
  },
  uninstall_skill: {
    toolName: "uninstall_skill",
    group: "skill",
    tag: "uninstall",
    isExplore: false,
    contentMode: "static",
    icon: Puzzle,
    getTitle: () => "卸载技能",
    getDetail: (message) => {
      const data = getStreamingData(message);
      return asString(data.name) ?? asString(data.skill_id);
    },
    render: (message) => (
      <SkillToolMessage
        message={message}
        actionLabel="卸载技能"
        emptyTitle="未返回技能卸载信息"
      />
    ),
  },
} satisfies Record<RegisteredToolName, ToolDescriptor>;

export function getToolDescriptor(toolName?: string): ToolDescriptor | null {
  if (!toolName) return null;
  const descriptor = TOOL_REGISTRY[toolName as RegisteredToolName] ?? null;
  if (!descriptor) return null;
  const isExplore = isExploreToolName(toolName);
  return descriptor.isExplore === isExplore ? descriptor : { ...descriptor, isExplore };
}

export function getRegisteredToolNames(): readonly RegisteredToolName[] {
  return REGISTERED_TOOL_NAMES;
}

export function getExploreToolNames(): RegisteredToolName[] {
  return getCatalogExploreToolNames();
}
