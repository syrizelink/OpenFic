import { Box, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { Check, Copy } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { toast } from "@/components";
import type {
  ChapterDiffLine,
  ChapterDiffSection,
  ChapterDiffSectionType,
} from "@/features/assistant/lib/chapter-tool-preview";
import {
  buildChapterDiffCopyText,
  getChapterDiffDisplayLineNumber,
  summarizeChapterDiffSection,
} from "@/features/assistant/lib/chapter-tool-preview";
import i18n from "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import { ToolBody, ToolNotice, ToolTextBlock } from "../shared/tool-message-shared";
import {
  asString,
  getCharacterPayload,
  getToolResultData,
  getToolResultMessage,
  isRecord,
} from "../shared/tool-message-utils";

interface CharacterToolMessageProps {
  message: AgentMessage;
}

interface CharacterDiffPreview {
  character_id?: string;
  character_name?: string;
  sections: ChapterDiffSection[];
}

const COPY_FEEDBACK_MS = 1200;

function normalizeDiffLineType(value: unknown): ChapterDiffLine["type"] {
  if (value === "added" || value === "removed") return value;
  return "context";
}

function normalizeDiffSectionType(value: unknown): ChapterDiffSectionType | null {
  if (value === "content" || value === "title") return value;
  return null;
}

function getCharacterDiffPreview(message: AgentMessage): CharacterDiffPreview | null {
  const data = getToolResultData(message);
  if (!isRecord(data)) return null;
  const rawPreview = data.character_diff;
  if (!isRecord(rawPreview) || !Array.isArray(rawPreview.sections)) return null;

  return {
    character_id: asString(rawPreview.character_id),
    character_name: asString(rawPreview.character_name),
    sections: rawPreview.sections
      .filter(isRecord)
      .map((section) => {
        const sectionType = normalizeDiffSectionType(section.type);
        if (!sectionType) return null;
        return {
          type: sectionType,
          lines: Array.isArray(section.lines)
            ? section.lines.filter(isRecord).map((line) => ({
                type: normalizeDiffLineType(line.type),
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

export function CharacterToolMessage({ message }: CharacterToolMessageProps) {
  const character = getCharacterPayload(message);
  const diffPreview = getCharacterDiffPreview(message);
  const copyFeedbackTimerRef = useRef<number | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(
    () => () => {
      if (copyFeedbackTimerRef.current !== null) {
        window.clearTimeout(copyFeedbackTimerRef.current);
      }
    },
    [],
  );

  if (diffPreview) {
    const contentSection =
      diffPreview.sections.find((section) => section.type === "content") ?? null;
    const changeSummary = summarizeChapterDiffSection(contentSection);
    const copyText = buildChapterDiffCopyText(contentSection);

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
          <Flex
            align="center"
            justify="between"
            gap="2"
            className="agent-chapter-diff-card-header"
          >
            <Flex
              align="center"
              gap="2"
              className="agent-chapter-diff-card-meta"
            >
              <Text className="agent-chapter-diff-card-title">
                {diffPreview.character_name ?? character.name ?? i18n.t("assistant.tools.character")}
              </Text>
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
                  +{changeSummary.added}
                </Text>
                <Text
                  size="1"
                  className="agent-chapter-tool-change"
                  data-change="removed"
                >
                  -{changeSummary.removed}
                </Text>
              </Flex>
            </Flex>
            <Tooltip
              content={isCopied ? i18n.t("common.copied") : i18n.t("assistant.tools.copyDiff")}
            >
              <IconButton
                size="1"
                variant="ghost"
                color={isCopied ? "green" : "gray"}
                aria-label={
                  isCopied
                    ? i18n.t("assistant.tools.diffCopied")
                    : i18n.t("assistant.tools.copyDiff")
                }
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
                {contentSection?.lines.length ? (
                  contentSection.lines.map((line, index) => (
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
                  ))
                ) : (
                  <div className="agent-chapter-diff-empty">
                    {i18n.t("assistant.tools.noBodyDiff")}
                  </div>
                )}
              </div>
            </Box>
          </Box>
        </Box>
      </ToolBody>
    );
  }

  if (!character.name && !character.description) {
    return (
      <ToolBody>
        <ToolNotice title={i18n.t("assistant.tools.noCharacterInfo")}>
          {getToolResultMessage(message) ?? i18n.t("assistant.tools.noCharacterInfoDescription")}
        </ToolNotice>
      </ToolBody>
    );
  }

  return (
    <ToolBody>
      <ToolTextBlock
        label={i18n.t("assistant.tools.character")}
        value={character.name}
      />
      <ToolTextBlock
        label={i18n.t("assistant.tools.description")}
        value={character.description}
      />
      <ToolTextBlock
        label={i18n.t("assistant.tools.result")}
        value={getToolResultMessage(message)}
      />
    </ToolBody>
  );
}
