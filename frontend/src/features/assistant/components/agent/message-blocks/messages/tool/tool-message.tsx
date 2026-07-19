import { Box, Flex, Text, Tooltip } from "@radix-ui/themes";
import { AlertTriangle, CircleAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import {
  formatChapterDisplayName,
  getChapterDiffBodySection,
  getChapterDiffPreview,
  summarizeChapterDiffSection,
  type ChapterDiffSection,
  type ChapterDiffSectionType,
} from "@/features/assistant/lib/chapter-tool-preview";
import i18n from "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import {
  MessageBlockContent,
  MessageBlockHeader,
  MessageBlockHeaderMain,
  MessageBlockMeta,
  MessageBlockShell,
  MessageExpandButton,
} from "../../shared/message-shell";
import { joinClassNames } from "../../shared/message-shell-utils";
import { getToolDescriptor } from "../../tools/shared/tool-message-registry";
import { UnregisteredToolMessage } from "../../tools/shared/tool-message-status";
import {
  getChapterPayload,
  getNotePayload,
  getToolErrorMessage,
  getWorldEntryPayload,
  resolveToolMessageVisibilityState,
} from "../../tools/shared/tool-message-utils";

interface ToolMessageProps {
  message: AgentMessage;
}

interface ToolErrorIndicatorProps {
  errorMessage: string;
}

export function ToolErrorIndicator({ errorMessage }: ToolErrorIndicatorProps) {
  return (
    <Tooltip content={<Box className="agent-tool-error-tooltip">{errorMessage}</Box>}>
      <Box
        className="agent-tool-error-indicator"
        aria-label={errorMessage}
      >
        <CircleAlert size={14} />
      </Box>
    </Tooltip>
  );
}

function isChapterDiffTool(message: AgentMessage): boolean {
  return (
    message.toolName === "write_chapter" ||
    message.toolName === "edit_chapter" ||
    message.toolName === "delete_chapter"
  );
}

function isNoteDiffTool(message: AgentMessage): boolean {
  return (
    message.toolName === "write_note" ||
    message.toolName === "edit_note" ||
    message.toolName === "delete_note" ||
    message.toolName === "move_note"
  );
}

function isWorldEntryDiffTool(message: AgentMessage): boolean {
  return (
    message.toolName === "create_world_entry" ||
    message.toolName === "edit_world_entry" ||
    message.toolName === "delete_world_entry"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function normalizeSectionType(value: unknown): ChapterDiffSectionType | null {
  if (value === "content" || value === "title") return value;
  return null;
}

function getToolResultDataRecord(message: AgentMessage): Record<string, unknown> | null {
  const resultData = message.toolResult?.data;
  if (isRecord(resultData)) return resultData;
  return isRecord(message.toolResult) ? message.toolResult : null;
}

function getNoteDiffPreview(message: AgentMessage): {
  note_title?: string;
  note_id?: string;
  sections: ChapterDiffSection[];
} | null {
  const data = getToolResultDataRecord(message);
  if (!data) return null;
  const metadata = data.metadata;
  if (!isRecord(metadata)) return null;
  const rawPreview = metadata.note_diff;
  if (!isRecord(rawPreview) || !Array.isArray(rawPreview.sections)) return null;
  return {
    note_title: asString(rawPreview.note_title),
    note_id: asString(rawPreview.note_id),
    sections: rawPreview.sections
      .filter(isRecord)
      .map((section) => {
        const sectionType = normalizeSectionType(section.type);
        if (!sectionType) return null;
        return {
          type: sectionType,
          lines: Array.isArray(section.lines)
            ? section.lines.filter(isRecord).map((line) => ({
                type: (line.type === "added" || line.type === "removed"
                  ? line.type
                  : "context") as ChapterDiffSection["lines"][0]["type"],
                before_line_number:
                  typeof line.before_line_number === "number" ? line.before_line_number : null,
                after_line_number:
                  typeof line.after_line_number === "number" ? line.after_line_number : null,
                text: typeof line.text === "string" ? line.text : "",
              }))
            : [],
        };
      })
      .filter((section): section is ChapterDiffSection => section !== null),
  };
}

function getWorldEntryDiffPreview(message: AgentMessage): {
  entry_title?: string;
  entry_id?: string;
  sections: ChapterDiffSection[];
} | null {
  const data = getToolResultDataRecord(message);
  if (!data) return null;
  const metadata = data.metadata;
  if (!isRecord(metadata)) return null;
  const rawPreview = metadata.world_entry_diff;
  if (!isRecord(rawPreview) || !Array.isArray(rawPreview.sections)) return null;
  return {
    entry_title: asString(rawPreview.entry_title),
    entry_id: asString(rawPreview.entry_id),
    sections: rawPreview.sections
      .filter(isRecord)
      .map((section) => {
        const sectionType = normalizeSectionType(section.type);
        if (!sectionType) return null;
        return {
          type: sectionType,
          lines: Array.isArray(section.lines)
            ? section.lines.filter(isRecord).map((line) => ({
                type: (line.type === "added" || line.type === "removed"
                  ? line.type
                  : "context") as ChapterDiffSection["lines"][0]["type"],
                before_line_number:
                  typeof line.before_line_number === "number" ? line.before_line_number : null,
                after_line_number:
                  typeof line.after_line_number === "number" ? line.after_line_number : null,
                text: typeof line.text === "string" ? line.text : "",
              }))
            : [],
        };
      })
      .filter((section): section is ChapterDiffSection => section !== null),
  };
}

export function ToolMessage({ message }: ToolMessageProps) {
  const descriptor = getToolDescriptor(message.toolName);
  const errorMessage = getToolErrorMessage(message);
  const isIncompleteAskUser =
    message.toolName === "ask_user" && message.status !== "completed" && message.status !== "error";
  const isRunning = Boolean(
    message.isStreaming || message.status === "running" || isIncompleteAskUser,
  );
  const chapterDiffPreview = isChapterDiffTool(message) ? getChapterDiffPreview(message) : null;
  const noteDiffPreview = isNoteDiffTool(message) ? getNoteDiffPreview(message) : null;
  const worldEntryDiffPreview = isWorldEntryDiffTool(message)
    ? getWorldEntryDiffPreview(message)
    : null;
  const usesDiffHeader = Boolean(chapterDiffPreview || noteDiffPreview || worldEntryDiffPreview);
  const contentMode = usesDiffHeader ? "expandable" : (descriptor?.contentMode ?? "static");
  const defaultExpanded = descriptor?.defaultExpanded?.(message) ?? false;
  const [isExpanded, setIsExpanded] = useState(() => defaultExpanded);
  const content = !descriptor ? (
    <UnregisteredToolMessage
      toolName={message.toolName}
      errorMessage={errorMessage}
    />
  ) : contentMode === "hidden" ? null : !descriptor.render ? null : (
    descriptor.render(message)
  );
  const Icon = descriptor?.icon ?? AlertTriangle;
  const title = descriptor?.getTitle(message) ?? i18n.t("assistant.tools.unregisteredTool");
  const detail = descriptor
    ? descriptor.getDetail?.(message)
    : (message.toolName ?? i18n.t("assistant.tools.unknown"));
  const chapterDiffBodySection = getChapterDiffBodySection(chapterDiffPreview);
  const noteDiffBodySection = noteDiffPreview?.sections.find((s) => s.type === "content") ?? null;
  const worldEntryDiffBodySection =
    worldEntryDiffPreview?.sections.find((s) => s.type === "content") ?? null;
  const diffBodySection =
    chapterDiffBodySection ?? noteDiffBodySection ?? worldEntryDiffBodySection;
  const diffChangeSummary = summarizeChapterDiffSection(diffBodySection);
  const chapter = getChapterPayload(message);
  const note = isNoteDiffTool(message) ? getNotePayload(message) : null;
  const worldEntry = isWorldEntryDiffTool(message) ? getWorldEntryPayload(message) : null;
  const showCollapsedDiffMeta = usesDiffHeader && !isExpanded;
  const diffDetail = chapterDiffPreview
    ? formatChapterDisplayName({
        order: chapterDiffPreview.order,
        title: chapterDiffPreview.chapter_title ?? chapter.title,
        chapterId: chapterDiffPreview.chapter_id ?? chapter.chapter_id,
      })
    : noteDiffPreview
      ? (noteDiffPreview.note_title ?? note?.title)
      : worldEntryDiffPreview
        ? (worldEntryDiffPreview.entry_title ?? worldEntry?.title)
        : undefined;
  const visibilityState = resolveToolMessageVisibilityState({
    message,
    contentMode,
    hasContent: Boolean(content),
    hasDetail: Boolean(detail),
    errorMessage,
  });
  const titleClassName = joinClassNames(
    "agent-tool-title",
    "agent-message-shell-title",
    isRunning && "text-shimmer",
    visibilityState.showErrorIndicator && "agent-message-shell-title--error",
  );
  const iconClassName = joinClassNames(
    "agent-message-icon",
    "agent-message-shell-icon",
    visibilityState.showErrorIndicator && "agent-message-shell-icon--error",
  );
  const showMeta =
    visibilityState.showErrorIndicator ||
    usesDiffHeader ||
    visibilityState.showDetail ||
    visibilityState.showExpandButton;

  const handleToggleExpanded = () => {
    if (!visibilityState.canExpand) return;
    setIsExpanded((value) => !value);
  };

  return (
    <MessageBlockShell
      expandable={visibilityState.canExpand}
      isStreaming={message.isStreaming}
      status={message.status ?? "completed"}
      flush
      data-tool-name={message.toolName ?? "tool"}
      data-tool-group={descriptor?.group ?? "unknown"}
      data-tool-tag={descriptor?.tag ?? "unknown"}
      data-tool-explore={descriptor?.isExplore ? "true" : "false"}
      data-tool-registered={descriptor ? "true" : "false"}
    >
      <MessageBlockHeader
        expandable={visibilityState.canExpand}
        expanded={isExpanded}
        onToggle={handleToggleExpanded}
      >
        <MessageBlockHeaderMain>
          <Icon
            size={16}
            className={iconClassName}
          />
          <Text
            size="1"
            weight="medium"
            className={titleClassName}
            data-text={title}
          >
            {title}
          </Text>
          {showMeta ? (
            <MessageBlockMeta>
              {visibilityState.showErrorIndicator && errorMessage ? (
                <ToolErrorIndicator errorMessage={errorMessage} />
              ) : usesDiffHeader ? (
                <AnimatePresence initial={false}>
                  {showCollapsedDiffMeta ? (
                    <motion.div
                      key="diff-meta"
                      className="agent-chapter-tool-meta-shell"
                      initial={{ width: 0, opacity: 0, x: -4 }}
                      animate={{ width: "auto", opacity: 1, x: 0 }}
                      exit={{ width: 0, opacity: 0, x: -4 }}
                      transition={{
                        width: { duration: 0.18, ease: [0.22, 1, 0.36, 1] },
                        opacity: { duration: 0.14, ease: "easeOut" },
                        x: { duration: 0.18, ease: [0.22, 1, 0.36, 1] },
                      }}
                    >
                      <Flex
                        align="center"
                        gap="2"
                        className="agent-chapter-tool-meta-content"
                      >
                        {diffDetail ? (
                          <Text
                            size="1"
                            color="gray"
                            className="agent-tool-detail agent-message-shell-detail"
                          >
                            {diffDetail}
                          </Text>
                        ) : null}
                        <Flex
                          align="center"
                          gap="1"
                          className="agent-chapter-tool-stats"
                        >
                          <Text
                            size="1"
                            className="agent-chapter-tool-change"
                            data-change="added"
                          >
                            +{diffChangeSummary.added}
                          </Text>
                          <Text
                            size="1"
                            className="agent-chapter-tool-change"
                            data-change="removed"
                          >
                            -{diffChangeSummary.removed}
                          </Text>
                        </Flex>
                      </Flex>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              ) : visibilityState.showDetail && detail ? (
                <Text
                  size="1"
                  color="gray"
                  className="agent-tool-detail agent-message-shell-detail"
                >
                  {detail}
                </Text>
              ) : null}
              {visibilityState.showExpandButton ? (
                <MessageExpandButton
                  expanded={isExpanded}
                  label={
                    isExpanded
                      ? i18n.t("assistant.collapseToolMessage")
                      : i18n.t("assistant.expandToolMessage")
                  }
                />
              ) : null}
            </MessageBlockMeta>
          ) : null}
        </MessageBlockHeaderMain>
      </MessageBlockHeader>
      {visibilityState.showStaticContent ? (
        <Box
          className="agent-tool-content-shell"
          data-static="true"
        >
          <Box className="agent-tool-content">{content}</Box>
        </Box>
      ) : null}
      <MessageBlockContent
        motionKey="tool-content"
        visible={visibilityState.canExpand && isExpanded}
      >
        {content}
      </MessageBlockContent>
    </MessageBlockShell>
  );
}
