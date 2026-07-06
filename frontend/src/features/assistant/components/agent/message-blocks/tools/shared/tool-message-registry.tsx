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
  Trash2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
/* oxlint-disable react-refresh/only-export-components */
import type { ReactNode } from "react";

import { formatChapterDisplayName } from "@/features/assistant/lib/chapter-tool-preview";
import i18n from "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import { AskUserToolMessage } from "../ask-user/ask-user-tool-message";
import { CharacterToolMessage } from "../character/character-tool-message";
import { ChapterToolMessage } from "../chapter/chapter-tool-message";
import { EditNoteToolMessage, WriteNoteToolMessage } from "../note/note-tool-message";
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
import {
  getRecycleSubagentDetail,
  getRecycleSubagentTitle,
} from "../orchestration/recycle-subagent-tool-message";
import { PlanToolMessage } from "../plan/plan-tool-message";
import { getPlanToolDisplayConfig } from "../plan/plan-tool-message.utils";
import { WorldEntryToolMessage } from "../world-entry/world-entry-tool-message";
import {
  getExploreToolNames as getCatalogExploreToolNames,
  REGISTERED_TOOL_NAMES,
  isExploreToolName,
  type RegisteredToolName,
  type ToolContentMode,
  type ToolGroup,
} from "./tool-message-catalog";
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
  getCharacterList,
  getCharacterPayload,
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
  getWorldEntryList,
  getWorldEntryPayload,
  isRecord,
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
  detailKind: ReturnType<typeof getPlanToolDisplayConfig>["detailKind"],
): string | undefined {
  return detailKind === "count" ? getPlanCountDetail(message) : getPlanTopicDetail(message);
}

function getVolumeRefLabel(message: AgentMessage, key: string): string | undefined {
  const ref = getToolRef(message, key);
  return asString(ref?.title) ?? formatVolumeRefLabel(ref);
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
    getTitle: () => i18n.t("assistant.tools.readChapter"),
    getDetail: (message) => getReadChapterDetail(message),
  },
  write_chapter: {
    toolName: "write_chapter",
    group: "chapter",
    tag: "write",
    isExplore: false,
    contentMode: "expandable",
    icon: FilePenLine,
    getTitle: () => i18n.t("assistant.tools.writeChapter"),
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
    getTitle: () => i18n.t("assistant.tools.editChapter"),
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
    getTitle: () => i18n.t("assistant.tools.deleteChapter"),
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
    getTitle: () => i18n.t("assistant.tools.listNotes"),
    getDetail: (message) => {
      const items = getNoteItemList(message);
      return items.length > 0
        ? i18n.t("assistant.tools.itemCount", { count: items.length })
        : undefined;
    },
  },
  read_note: {
    toolName: "read_note",
    group: "note",
    tag: "read",
    isExplore: true,
    contentMode: "hidden",
    icon: BookOpen,
    getTitle: () => i18n.t("assistant.tools.readNote"),
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
    getTitle: () => i18n.t("assistant.tools.writeNote"),
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
    getTitle: () => i18n.t("assistant.tools.editNote"),
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
    getTitle: () => i18n.t("assistant.tools.deleteNote"),
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
    getTitle: () => i18n.t("assistant.tools.moveNote"),
    getDetail: (message) => {
      const note = getNotePayload(message);
      const noteLabel = note.title ?? formatNoteRefLabel(getToolRef(message, "note_ref"));
      const data = message.toolResult?.data;
      const target = isRecord(data) && isRecord(data.target_category) ? data.target_category : null;
      const targetLabel =
        asString(target?.title) ??
        formatCategoryRefLabel(getToolRef(message, "target_category_ref")) ??
        i18n.t("assistant.tools.rootLevel");
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
    getTitle: () => i18n.t("assistant.tools.createCategory"),
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
    getTitle: () => i18n.t("assistant.tools.listChapters"),
    getDetail: (message) => {
      const chapters = getChapterList(message);
      return chapters.length > 0
        ? i18n.t("assistant.tools.chapterCount", { count: chapters.length })
        : undefined;
    },
  },
  search_chapters: {
    toolName: "search_chapters",
    group: "chapter",
    tag: "search",
    isExplore: true,
    contentMode: "hidden",
    icon: FileSearch,
    getTitle: () => i18n.t("assistant.tools.searchChapters"),
    getDetail: (message) => {
      const data = getToolResultData(message);
      if (!isRecord(data)) return undefined;
      const results = Array.isArray(data.results) ? data.results : [];
      if (results.length === 0) return undefined;
      const query = typeof data.query === "string" && data.query ? data.query : undefined;
      return query
        ? `${query} · ${i18n.t("assistant.tools.matchCount", { count: results.length })}`
        : i18n.t("assistant.tools.matchedChapters", { count: results.length });
    },
  },
  update_index: {
    toolName: "update_index",
    group: "chapter",
    tag: "update-index",
    isExplore: false,
    contentMode: "hidden",
    icon: FileSearch,
    getTitle: () => i18n.t("assistant.tools.updateIndex"),
  },
  list_volumes: {
    toolName: "list_volumes",
    group: "volume",
    tag: "list",
    isExplore: true,
    contentMode: "hidden",
    icon: ListOrdered,
    getTitle: () => i18n.t("assistant.tools.listVolumes"),
    getDetail: (message) => {
      const volumes = getVolumeList(message);
      return volumes.length > 0
        ? i18n.t("assistant.tools.volumeCount", { count: volumes.length })
        : undefined;
    },
  },
  create_volume: {
    toolName: "create_volume",
    group: "volume",
    tag: "create",
    isExplore: false,
    contentMode: "hidden",
    icon: FileText,
    getTitle: () => i18n.t("assistant.tools.createVolume"),
    getDetail: (message) =>
      getVolumePayload(message)?.title ?? asString(getStreamingData(message).title),
  },
  edit_volume: {
    toolName: "edit_volume",
    group: "volume",
    tag: "edit",
    isExplore: false,
    contentMode: "hidden",
    icon: FilePenLine,
    getTitle: () => i18n.t("assistant.tools.editVolume"),
    getDetail: (message) => {
      const sourceLabel = getVolumeRefLabel(message, "volume_ref");
      const targetLabel =
        getVolumePayload(message)?.title ?? asString(getStreamingData(message).new_title);
      if (sourceLabel && targetLabel) return `${sourceLabel} \u2192 ${targetLabel}`;
      return targetLabel ?? sourceLabel;
    },
  },
  delete_volume: {
    toolName: "delete_volume",
    group: "volume",
    tag: "delete",
    isExplore: false,
    contentMode: "hidden",
    icon: Trash2,
    getTitle: () => i18n.t("assistant.tools.deleteVolume"),
    getDetail: (message) => getVolumeRefLabel(message, "volume_ref"),
  },
  move_chapter_to_volume: {
    toolName: "move_chapter_to_volume",
    group: "volume",
    tag: "move",
    isExplore: false,
    contentMode: "hidden",
    icon: FilePenLine,
    getTitle: () => i18n.t("assistant.tools.moveChapterToVolume"),
    getDetail: (message) => {
      const chapterLabel =
        getChapterPayload(message).title ??
        formatChapterRefLabel(getToolRef(message, "chapter_ref"));
      const targetLabel = getVolumeRefLabel(message, "target_volume_ref");
      if (chapterLabel && targetLabel) return `${chapterLabel} \u2192 ${targetLabel}`;
      return chapterLabel ?? targetLabel;
    },
  },
  read_chapter_summaries: {
    toolName: "read_chapter_summaries",
    group: "context",
    tag: "chapter-summary",
    isExplore: true,
    contentMode: "hidden",
    icon: FileSearch,
    getTitle: () => i18n.t("assistant.tools.chapterSummaries"),
    getDetail: (message) => {
      const summaries = getChapterSummaryList(message);
      return summaries.length > 0
        ? i18n.t("assistant.tools.summaryCount", { count: summaries.length })
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
    getTitle: () => i18n.t("assistant.tools.rangeSummaries"),
    getDetail: (message) => {
      const summaries = getRangeSummaryList(message);
      return summaries.length > 0
        ? i18n.t("assistant.tools.summaryCount", { count: summaries.length })
        : formatRangeSummaryQuery(message);
    },
  },
  list_characters: {
    toolName: "list_characters",
    group: "context",
    tag: "character-list",
    isExplore: true,
    contentMode: "hidden",
    icon: ListOrdered,
    getTitle: () => i18n.t("assistant.tools.listCharacters"),
    getDetail: (message) => {
      const characters = getCharacterList(message);
      return characters.length > 0
        ? i18n.t("assistant.tools.characterCount", { count: characters.length })
        : undefined;
    },
  },
  read_character: {
    toolName: "read_character",
    group: "context",
    tag: "character-read",
    isExplore: true,
    contentMode: "hidden",
    icon: BookOpen,
    getTitle: () => i18n.t("assistant.tools.readCharacter"),
    getDetail: (message) => getCharacterPayload(message).name,
  },
  list_world_entries: {
    toolName: "list_world_entries",
    group: "context",
    tag: "world-entry-list",
    isExplore: true,
    contentMode: "hidden",
    icon: ListOrdered,
    getTitle: () => i18n.t("assistant.tools.listWorldEntries"),
    getDetail: (message) => {
      const entries = getWorldEntryList(message);
      return entries.length > 0
        ? i18n.t("assistant.tools.worldEntryCount", { count: entries.length })
        : undefined;
    },
  },
  read_world_entry: {
    toolName: "read_world_entry",
    group: "context",
    tag: "world-entry-read",
    isExplore: true,
    contentMode: "hidden",
    icon: BookOpen,
    getTitle: () => i18n.t("assistant.tools.readWorldEntry"),
    getDetail: (message) => getWorldEntryPayload(message).title,
  },
  create_world_entry: {
    toolName: "create_world_entry",
    group: "context",
    tag: "world-entry-create",
    isExplore: false,
    contentMode: "expandable",
    icon: FilePenLine,
    getTitle: () => i18n.t("assistant.tools.createWorldEntry"),
    getDetail: (message) => getWorldEntryPayload(message).title,
    defaultExpanded: () => true,
    render: (message) => <WorldEntryToolMessage message={message} />,
  },
  edit_world_entry: {
    toolName: "edit_world_entry",
    group: "context",
    tag: "world-entry-edit",
    isExplore: false,
    contentMode: "expandable",
    icon: FilePenLine,
    getTitle: () => i18n.t("assistant.tools.editWorldEntry"),
    getDetail: (message) => getWorldEntryPayload(message).title,
    defaultExpanded: () => true,
    render: (message) => <WorldEntryToolMessage message={message} />,
  },
  delete_world_entry: {
    toolName: "delete_world_entry",
    group: "context",
    tag: "world-entry-delete",
    isExplore: false,
    contentMode: "hidden",
    icon: Trash2,
    getTitle: () => i18n.t("assistant.tools.deleteWorldEntry"),
    getDetail: (message) => getWorldEntryPayload(message).title,
  },
  create_character: {
    toolName: "create_character",
    group: "context",
    tag: "character-create",
    isExplore: false,
    contentMode: "expandable",
    icon: FilePenLine,
    getTitle: () => i18n.t("assistant.tools.createCharacter"),
    getDetail: (message) => getCharacterPayload(message).name,
    defaultExpanded: () => true,
    render: (message) => <CharacterToolMessage message={message} />,
  },
  edit_character: {
    toolName: "edit_character",
    group: "context",
    tag: "character-edit",
    isExplore: false,
    contentMode: "expandable",
    icon: FilePenLine,
    getTitle: () => i18n.t("assistant.tools.editCharacter"),
    getDetail: (message) => getCharacterPayload(message).name,
    defaultExpanded: () => true,
    render: (message) => <CharacterToolMessage message={message} />,
  },
  delete_character: {
    toolName: "delete_character",
    group: "context",
    tag: "character-delete",
    isExplore: false,
    contentMode: "hidden",
    icon: Trash2,
    getTitle: () => i18n.t("assistant.tools.deleteCharacter"),
    getDetail: (message) => getCharacterPayload(message).name,
  },
  create_plan: {
    toolName: "create_plan",
    group: "plan",
    tag: "create",
    isExplore: false,
    contentMode: getPlanToolDisplayConfig("create_plan").contentMode,
    icon: ListOrdered,
    getTitle: () => i18n.t("assistant.tools.createPlan"),
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
    getTitle: () => i18n.t("assistant.tools.updatePlan"),
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
    getTitle: () => i18n.t("assistant.tools.getPlan"),
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
    getTitle: () => i18n.t("assistant.tools.listPlan"),
    getDetail: (message) =>
      getPlanDetailForDisplayKind(message, getPlanToolDisplayConfig("list_plan").detailKind),
    render: (message) => <PlanToolMessage message={message} />,
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
