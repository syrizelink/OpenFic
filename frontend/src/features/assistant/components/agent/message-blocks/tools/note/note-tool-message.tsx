import { useEffect, useRef, useState } from "react";
import { Box, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { Check, Copy } from "lucide-react";

import type { AgentMessage } from "@/lib/agent.types";
import i18n from "@/i18n";
import type { ChapterDiffLine, ChapterDiffSection } from "@/features/assistant/lib/chapter-tool-preview";
import {
  buildChapterDiffCopyText,
  getChapterDiffDisplayLineNumber,
  summarizeChapterDiffSection,
} from "@/features/assistant/lib/chapter-tool-preview";
import { toast } from "@/components";

import {
  asString,
  getNotePayload,
  getToolResultMessage,
} from "../shared/tool-message-utils";
import {
  ToolBody,
  ToolNotice,
  ToolTextBlock,
} from "../shared/tool-message-shared";

interface NoteToolMessageProps {
  message: AgentMessage;
}

interface NoteDiffPreview {
  operation: "create" | "update";
  note_id?: string;
  note_title?: string;
  sections: ChapterDiffSection[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function normalizeDiffLineType(value: unknown): ChapterDiffLine["type"] {
  if (value === "added" || value === "removed") return value;
  return "context";
}

function getToolResultDataRecord(message: AgentMessage): Record<string, unknown> | null {
  const resultData = message.toolResult?.data;
  if (isRecord(resultData)) return resultData;
  return isRecord(message.toolResult) ? message.toolResult : null;
}

function getNoteDiffPreview(message: AgentMessage): NoteDiffPreview | null {
  const data = getToolResultDataRecord(message);
  if (!data) return null;
  const rawPreview = data.note_diff;
  if (!isRecord(rawPreview) || !Array.isArray(rawPreview.sections)) return null;

  return {
    operation: rawPreview.operation === "create" ? "create" : "update",
    note_id: asString(rawPreview.note_id),
    note_title: asString(rawPreview.note_title),
    sections: rawPreview.sections
      .filter(isRecord)
      .map((section) => ({
        label: asString(section.label) ?? "",
        lines: Array.isArray(section.lines)
          ? section.lines.filter(isRecord).map((line) => ({
            type: normalizeDiffLineType(line.type),
            before_line_number: typeof line.before_line_number === "number" ? line.before_line_number : null,
            after_line_number: typeof line.after_line_number === "number" ? line.after_line_number : null,
            text: typeof line.text === "string" ? line.text : "",
          }))
          : [],
      }))
      .filter((section) => section.label),
  };
}

const COPY_FEEDBACK_MS = 1200;

function NoteSummary({ message, emptyTitle, emptyDescription }: NoteToolMessageProps & {
  emptyTitle: string;
  emptyDescription: string;
}) {
  const note = getNotePayload(message);

  if (!note.title) {
    return (
      <ToolNotice title={emptyTitle}>
        {getToolResultMessage(message) ?? emptyDescription}
      </ToolNotice>
    );
  }

  return (
    <>
      <ToolTextBlock label="笔记" value={note.title} />
      {note.content ? <ToolTextBlock label="内容" value={note.content} /> : null}
      <ToolTextBlock label="结果" value={getToolResultMessage(message)} />
    </>
  );
}

export function WriteNoteToolMessage({ message }: NoteToolMessageProps) {
  const note = getNotePayload(message);
  const diffPreview = getNoteDiffPreview(message);
  const copyFeedbackTimerRef = useRef<number | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => () => {
    if (copyFeedbackTimerRef.current !== null) {
      window.clearTimeout(copyFeedbackTimerRef.current);
    }
  }, []);

  if (diffPreview) {
    const contentSection = diffPreview.sections.find((s) => s.label === "内容") ?? null;
    const changeSummary = summarizeChapterDiffSection(contentSection);
    const copyText = buildChapterDiffCopyText(contentSection);

    const handleCopy = async () => {
      if (!copyText) {
        toast.error("没有可复制的正文 Diff");
        return;
      }
      try {
        await navigator.clipboard.writeText(copyText);
        setIsCopied(true);
        if (copyFeedbackTimerRef.current !== null) {
          window.clearTimeout(copyFeedbackTimerRef.current);
        }
        copyFeedbackTimerRef.current = window.setTimeout(() => {
          setIsCopied(false);
          copyFeedbackTimerRef.current = null;
        }, COPY_FEEDBACK_MS);
        toast.success("已复制");
      } catch {
        toast.error("复制失败");
      }
    };

    return (
      <ToolBody>
        <Box className="agent-chapter-diff-card">
          <Flex align="center" justify="between" gap="2" className="agent-chapter-diff-card-header">
            <Flex align="center" gap="2" className="agent-chapter-diff-card-meta">
              <Text className="agent-chapter-diff-card-title">
                {diffPreview.note_title ?? note.title}
              </Text>
              <Flex align="center" gap="1" className="agent-chapter-tool-stats">
                <Text size="1" className="agent-chapter-tool-change" data-change="added">
                  +{changeSummary.added}
                </Text>
                <Text size="1" className="agent-chapter-tool-change" data-change="removed">
                  -{changeSummary.removed}
                </Text>
              </Flex>
            </Flex>
            <Tooltip content={isCopied ? "已复制" : "复制正文 Diff"}>
              <IconButton
                size="1"
                variant="ghost"
                color={isCopied ? "green" : "gray"}
                aria-label={isCopied ? "正文 Diff 已复制" : "复制正文 Diff"}
                className="agent-message-block-toolbar-button agent-chapter-diff-copy-button"
                data-copied={isCopied ? "true" : undefined}
                disabled={!copyText}
                onClick={handleCopy}
              >
                {isCopied ? <Check size={13} /> : <Copy size={13} />}
              </IconButton>
            </Tooltip>
          </Flex>
          <Box className="agent-chapter-diff-card-body">
            <Box className="agent-chapter-diff-scroll">
              <div className="agent-chapter-diff-lines">
                {contentSection?.lines.length ? contentSection.lines.map((line, index) => (
                  <div
                    key={`${index}-${line.before_line_number ?? "n"}-${line.after_line_number ?? "n"}`}
                    className="agent-chapter-diff-line"
                    data-type={line.type}
                  >
                    <span className="agent-chapter-diff-gutter">
                      {getChapterDiffDisplayLineNumber(line) ?? ""}
                    </span>
                    <span className="agent-chapter-diff-text">{line.text || " "}</span>
                  </div>
                )) : (
                  <div className="agent-chapter-diff-empty">
                    无可显示正文差异。
                  </div>
                )}
              </div>
            </Box>
          </Box>
        </Box>
      </ToolBody>
    );
  }

  return (
    <ToolBody>
      <NoteSummary
        message={message}
        emptyTitle="未返回新笔记信息"
        emptyDescription="这次创建没有返回可显示的笔记信息。"
      />
    </ToolBody>
  );
}

export function EditNoteToolMessage({ message }: NoteToolMessageProps) {
  const note = getNotePayload(message);
  const diffPreview = getNoteDiffPreview(message);
  const copyFeedbackTimerRef = useRef<number | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => () => {
    if (copyFeedbackTimerRef.current !== null) {
      window.clearTimeout(copyFeedbackTimerRef.current);
    }
  }, []);

  if (diffPreview) {
    const contentSection = diffPreview.sections.find((s) => s.label === "内容") ?? null;
    const changeSummary = summarizeChapterDiffSection(contentSection);
    const copyText = buildChapterDiffCopyText(contentSection);

    const handleCopy = async () => {
      if (!copyText) {
        toast.error("没有可复制的正文 Diff");
        return;
      }
      try {
        await navigator.clipboard.writeText(copyText);
        setIsCopied(true);
        if (copyFeedbackTimerRef.current !== null) {
          window.clearTimeout(copyFeedbackTimerRef.current);
        }
        copyFeedbackTimerRef.current = window.setTimeout(() => {
          setIsCopied(false);
          copyFeedbackTimerRef.current = null;
        }, COPY_FEEDBACK_MS);
        toast.success("已复制");
      } catch {
        toast.error("复制失败");
      }
    };

    return (
      <ToolBody>
        <Box className="agent-chapter-diff-card">
          <Flex align="center" justify="between" gap="2" className="agent-chapter-diff-card-header">
            <Flex align="center" gap="2" className="agent-chapter-diff-card-meta">
              <Text className="agent-chapter-diff-card-title">
                {diffPreview.note_title ?? note.title}
              </Text>
              <Flex align="center" gap="1" className="agent-chapter-tool-stats">
                <Text size="1" className="agent-chapter-tool-change" data-change="added">
                  +{changeSummary.added}
                </Text>
                <Text size="1" className="agent-chapter-tool-change" data-change="removed">
                  -{changeSummary.removed}
                </Text>
              </Flex>
            </Flex>
            <Tooltip content={isCopied ? "已复制" : "复制正文 Diff"}>
              <IconButton
                size="1"
                variant="ghost"
                color={isCopied ? "green" : "gray"}
                aria-label={isCopied ? "正文 Diff 已复制" : "复制正文 Diff"}
                className="agent-message-block-toolbar-button agent-chapter-diff-copy-button"
                data-copied={isCopied ? "true" : undefined}
                disabled={!copyText}
                onClick={handleCopy}
              >
                {isCopied ? <Check size={13} /> : <Copy size={13} />}
              </IconButton>
            </Tooltip>
          </Flex>
          <Box className="agent-chapter-diff-card-body">
            <Box className="agent-chapter-diff-scroll">
              <div className="agent-chapter-diff-lines">
                {contentSection?.lines.length ? contentSection.lines.map((line, index) => (
                  <div
                    key={`${index}-${line.before_line_number ?? "n"}-${line.after_line_number ?? "n"}`}
                    className="agent-chapter-diff-line"
                    data-type={line.type}
                  >
                    <span className="agent-chapter-diff-gutter">
                      {getChapterDiffDisplayLineNumber(line) ?? ""}
                    </span>
                    <span className="agent-chapter-diff-text">{line.text || " "}</span>
                  </div>
                )) : (
                  <div className="agent-chapter-diff-empty">
                    无可显示正文差异。
                  </div>
                )}
              </div>
            </Box>
          </Box>
        </Box>
      </ToolBody>
    );
  }

  const toolArgs = message.toolArgs ?? {};
  const oldContent = asString(toolArgs.old_content);
  const newContent = asString(toolArgs.new_content);

  if (!note.title && !oldContent && !newContent) {
    return (
      <ToolBody>
        <ToolNotice title={i18n.t("assistant.tools.noNoteEditInfo")}>
          {getToolResultMessage(message) ?? i18n.t("assistant.tools.noNoteEditInfoDescription")}
        </ToolNotice>
      </ToolBody>
    );
  }

  return (
    <ToolBody>
      <ToolTextBlock label={i18n.t("assistant.tools.note")} value={note.title} />
      <ToolTextBlock label={i18n.t("assistant.tools.find")} value={oldContent} />
      <ToolTextBlock label={i18n.t("assistant.tools.replaceWith")} value={newContent} />
      <ToolTextBlock label={i18n.t("assistant.tools.result")} value={getToolResultMessage(message)} />
    </ToolBody>
  );
}
