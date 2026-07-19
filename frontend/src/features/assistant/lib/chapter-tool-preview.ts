import type { AgentMessage } from "@/lib/agent.types";

export interface ChapterDiffLine {
  type: "context" | "added" | "removed";
  before_line_number: number | null;
  after_line_number: number | null;
  text: string;
}

export type ChapterDiffSectionType = "content" | "title";

export interface ChapterDiffSection {
  type: ChapterDiffSectionType;
  lines: ChapterDiffLine[];
}

export interface ChapterDiffPreview {
  operation: "create" | "update";
  chapter_id?: string;
  chapter_title?: string;
  order?: number;
  sections: ChapterDiffSection[];
}

export interface ChapterDiffChangeSummary {
  added: number;
  removed: number;
}

function normalizeChapterDiffLineType(value: unknown): ChapterDiffLine["type"] {
  if (value === "added" || value === "removed") return value;
  return "context";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function normalizeChapterDiffSectionType(value: unknown): ChapterDiffSectionType | null {
  if (value === "content" || value === "title") return value;
  return null;
}

function getDiffLinePrefix(type: ChapterDiffLine["type"]): string {
  if (type === "added") return "+";
  if (type === "removed") return "-";
  return " ";
}

function getToolResultDataRecord(message: AgentMessage): Record<string, unknown> | null {
  const resultData = message.toolResult?.data;
  if (isRecord(resultData)) return resultData;
  return isRecord(message.toolResult) ? message.toolResult : null;
}

export function getPreviewChapterRecord(message: AgentMessage): Record<string, unknown> | null {
  const data = getToolResultDataRecord(message);
  if (data && isRecord(data.chapter)) return data.chapter;
  return null;
}

export function getChapterDiffPreview(message: AgentMessage): ChapterDiffPreview | null {
  const data = getToolResultDataRecord(message);
  if (!data) return null;
  const metadata = data.metadata;
  if (!isRecord(metadata)) return null;
  const rawPreview = metadata.chapter_diff;
  if (!isRecord(rawPreview) || !Array.isArray(rawPreview.sections)) return null;

  return {
    operation: rawPreview.operation === "create" ? "create" : "update",
    chapter_id: asString(rawPreview.chapter_id),
    chapter_title: asString(rawPreview.chapter_title),
    order: typeof rawPreview.order === "number" ? rawPreview.order : undefined,
    sections: rawPreview.sections
      .filter(isRecord)
      .map((section) => {
        const sectionType = normalizeChapterDiffSectionType(section.type);
        if (!sectionType) return null;
        return {
          type: sectionType,
          lines: Array.isArray(section.lines)
            ? section.lines.filter(isRecord).map((line) => ({
                type: normalizeChapterDiffLineType(line.type),
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

export function getChapterDiffBodySection(
  preview: ChapterDiffPreview | null,
): ChapterDiffSection | null {
  if (!preview) return null;
  const contentSection = preview.sections.find((section) => section.type === "content");
  if (contentSection) return contentSection;
  return preview.sections.find((section) => section.type !== "title") ?? null;
}

export function summarizeChapterDiffSection(
  section: ChapterDiffSection | null | undefined,
): ChapterDiffChangeSummary {
  return (section?.lines ?? []).reduce<ChapterDiffChangeSummary>(
    (summary, line) => {
      if (line.type === "added") summary.added += 1;
      if (line.type === "removed") summary.removed += 1;
      return summary;
    },
    {
      added: 0,
      removed: 0,
    },
  );
}

export function getChapterDiffDisplayLineNumber(line: ChapterDiffLine): number | null {
  return line.after_line_number ?? line.before_line_number;
}

export function buildChapterDiffCopyText(section: ChapterDiffSection | null | undefined): string {
  return (section?.lines ?? [])
    .map((line) => `${getDiffLinePrefix(line.type)}${line.text}`)
    .join("\n");
}

export function formatChapterDisplayName(input: {
  order?: number;
  title?: string;
  chapterId?: string;
}): string | undefined {
  if (input.title) return input.title;
  if (typeof input.order === "number") {
    return `第${input.order}章`;
  }
  return input.chapterId;
}

export function createApprovalPreviewToolMessage(message: AgentMessage): AgentMessage | null {
  if (message.type !== "approval") return null;
  const payload = isRecord(message.payload) ? message.payload : {};
  const toolCallId = asString(payload.tool_call_id);
  const toolName = asString(payload.tool_name);
  const toolArgs = isRecord(payload.tool_args) ? payload.tool_args : {};
  const toolResultPreview = isRecord(payload.tool_result_preview)
    ? payload.tool_result_preview
    : null;
  if (!toolCallId || !toolName || !toolResultPreview) return null;

  return {
    id: toolCallId,
    correlationId: toolCallId,
    type: "tool",
    role: "tool",
    status: "completed",
    display: "list",
    timestamp: message.timestamp,
    payload: {
      tool_call_id: toolCallId,
      tool_name: toolName,
      tool_args: toolArgs,
      tool_result: toolResultPreview,
      success: true,
    },
    toolName,
    toolNames: [toolName],
    toolArgs,
    toolResult: toolResultPreview,
    toolSuccess: true,
    isStreaming: false,
  };
}
