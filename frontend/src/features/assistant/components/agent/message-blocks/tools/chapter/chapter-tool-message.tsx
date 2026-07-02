import { useEffect, useRef, useState } from "react";
import { Box, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { Check, Copy } from "lucide-react";

import type { AgentMessage } from "@/lib/agent.types";
import i18n from "@/i18n";
import {
  buildChapterDiffCopyText,
  formatChapterDisplayName,
  getChapterDiffBodySection,
  getChapterDiffDisplayLineNumber,
  getChapterDiffPreview,
  summarizeChapterDiffSection,
} from "@/features/assistant/lib/chapter-tool-preview";
import { toast } from "@/components";

import "./chapter-tool-message.css";

import {
  getChapterPayload,
  getToolResultMessage,
} from "../shared/tool-message-utils";
import {
  ToolBody,
  ToolNotice,
  ToolTextBlock,
} from "../shared/tool-message-shared";

interface ChapterToolMessageProps {
  message: AgentMessage;
}

const COPY_FEEDBACK_MS = 1200;

export function ChapterToolMessage({ message }: ChapterToolMessageProps) {
  const chapter = getChapterPayload(message);
  const diffPreview = getChapterDiffPreview(message);
  const diffSection = getChapterDiffBodySection(diffPreview);
  const isMutationTool = message.toolName === "write_chapter" || message.toolName === "edit_chapter";
  const copyFeedbackTimerRef = useRef<number | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => () => {
    if (copyFeedbackTimerRef.current !== null) {
      window.clearTimeout(copyFeedbackTimerRef.current);
    }
  }, []);

  if (diffPreview) {
    const chapterName = formatChapterDisplayName({
      order: diffPreview.order,
      title: diffPreview.chapter_title ?? chapter.title,
      chapterId: diffPreview.chapter_id ?? chapter.chapter_id,
    }) ?? i18n.t("assistant.tools.chapter");
    const chapterChangeSummary = summarizeChapterDiffSection(diffSection);
    const copyText = buildChapterDiffCopyText(diffSection);
    const isTitleOnlyChange =
      !diffSection &&
      diffPreview.sections.some((section) => section.type === "title");

    const handleCopy = async () => {
      if (!copyText) {
        toast.error(i18n.t("assistant.tools.noDiffToCopy"));
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
        toast.success(i18n.t("common.copied"));
      } catch {
        toast.error(i18n.t("assistant.copyFailed"));
      }
    };

    return (
      <ToolBody>
        <Box className="agent-chapter-diff-card">
          <Flex align="center" justify="between" gap="2" className="agent-chapter-diff-card-header">
            <Flex align="center" gap="2" className="agent-chapter-diff-card-meta">
              <Text className="agent-chapter-diff-card-title">
                {chapterName}
              </Text>
              <Flex align="center" gap="1" className="agent-chapter-tool-stats">
                <Text size="1" className="agent-chapter-tool-change" data-change="added">
                  +{chapterChangeSummary.added}
                </Text>
                <Text size="1" className="agent-chapter-tool-change" data-change="removed">
                  -{chapterChangeSummary.removed}
                </Text>
              </Flex>
            </Flex>
            <Tooltip content={isCopied ? i18n.t("common.copied") : i18n.t("assistant.tools.copyDiff")}>
              <IconButton
                size="1"
                variant="ghost"
                color={isCopied ? "green" : "gray"}
                aria-label={isCopied ? i18n.t("assistant.tools.diffCopied") : i18n.t("assistant.tools.copyDiff")}
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
                {diffSection?.lines.length ? diffSection.lines.map((line, index) => (
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
                    {isTitleOnlyChange ? i18n.t("assistant.tools.titleOnlyChange") : i18n.t("assistant.tools.noBodyDiff")}
                  </div>
                )}
              </div>
            </Box>
          </Box>
        </Box>
      </ToolBody>
    );
  }

  if (isMutationTool) {
    return (
      <ToolBody>
        <ToolNotice title={i18n.t("assistant.tools.noChapterDiff")}>
          {getToolResultMessage(message) ?? i18n.t("assistant.tools.noChapterDiffDescription")}
        </ToolNotice>
      </ToolBody>
    );
  }

  const chapterName = formatChapterDisplayName({
    order: chapter.order,
    title: chapter.title,
    chapterId: chapter.chapter_id,
  });

  return (
    <ToolBody>
      <ToolTextBlock label={i18n.t("assistant.tools.chapter")} value={chapterName} />
      <ToolTextBlock
        label={i18n.t("assistant.tools.wordCount")}
        value={typeof chapter.word_count === "number" ? i18n.t("assistant.tools.wordCountWithUnit", { count: chapter.word_count }) : undefined}
      />
      {chapter.content ? (
        <ToolTextBlock label={i18n.t("assistant.tools.content")} value={chapter.content} />
      ) : (
        <ToolNotice title={i18n.t("assistant.tools.noChapterContent")}>
          {getToolResultMessage(message) ?? i18n.t("assistant.tools.noChapterContentDescription")}
        </ToolNotice>
      )}
    </ToolBody>
  );
}
