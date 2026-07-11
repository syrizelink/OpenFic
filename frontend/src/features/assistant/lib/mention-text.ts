import type { AssistantMentionCandidate } from "@/lib/mention.types";
import { pinyinMatch } from "@/lib/pinyin-search";

export type { AssistantMentionCandidate } from "@/lib/mention.types";

export type AssistantMentionKind =
  | "volume"
  | "chapter"
  | "note"
  | "note_category"
  | "world_info_entry"
  | "character";

export interface AssistantMentionToken {
  raw: string;
  kind: AssistantMentionKind;
  attrs: Record<string, string>;
  body: string;
}

export type AssistantMentionSegment = string | AssistantMentionToken;

const MENTION_RE =
  /<of-mention\b(?<attrsSelf>[^<>]*?)\s*\/>|<of-mention\b(?<attrsBlock>[^<>]*?)>(?<body>.*?)<\/of-mention\s*>/gs;
const ATTR_RE = /([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"/g;

function inferMentionKind(attrs: Record<string, string>): AssistantMentionKind {
  if (attrs.volume_id?.trim()) return "volume";
  if (attrs.chapter_id?.trim()) return "chapter";
  if (attrs.note_id?.trim()) return "note";
  if (attrs.note_category_id?.trim()) return "note_category";
  if (attrs.world_info_entry_id?.trim()) return "world_info_entry";
  if (attrs.character_id?.trim()) return "character";
  return "chapter";
}

function isExpandedMention(token: AssistantMentionToken): boolean {
  return Boolean(token.attrs.line_start?.trim() && token.attrs.line_end?.trim());
}

function decodeMentionEntities(text: string): string {
  return text
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

function escapeMentionEntities(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeMentionAttribute(text: string): string {
  return escapeMentionEntities(text).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function parseAttrs(rawAttrs: string): Record<string, string> {
  return Array.from(rawAttrs.matchAll(ATTR_RE)).reduce<Record<string, string>>((result, match) => {
    const [, key, value] = match;
    if (!key) return result;
    result[key] = decodeMentionEntities(value ?? "");
    return result;
  }, {});
}

export function parseMentionText(text: string): AssistantMentionSegment[] {
  if (!text || !text.includes("<of-mention")) return [text];

  const segments: AssistantMentionSegment[] = [];
  let cursor = 0;

  for (const match of text.matchAll(MENTION_RE)) {
    const start = match.index ?? 0;
    const raw = match[0];
    if (!raw) continue;

    if (start > cursor) {
      segments.push(text.slice(cursor, start));
    }

    const attrs = parseAttrs((match.groups?.attrsSelf ?? match.groups?.attrsBlock ?? "").trim());
    const kind = inferMentionKind(attrs);
    segments.push({
      raw,
      kind,
      attrs,
      body: decodeMentionEntities(match.groups?.body ?? ""),
    });
    cursor = start + raw.length;
  }

  if (cursor < text.length) {
    segments.push(text.slice(cursor));
  }

  return segments;
}

function escapeHtml(text: string): string {
  return escapeMentionEntities(text);
}

function escapeHtmlAttr(text: string): string {
  return escapeHtml(text).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function buildMentionHtml(token: AssistantMentionToken): string {
  return (
    `<span data-assistant-mention="true"` +
    ` data-mention-kind="${escapeHtmlAttr(token.kind)}"` +
    ` data-mention-raw="${escapeHtmlAttr(token.raw)}"` +
    ` data-mention-label="${escapeHtmlAttr(getMentionDisplayLabel(token))}"` +
    ` data-mention-body="${escapeHtmlAttr(token.body)}"` +
    ` data-mention-volume-id="${escapeHtmlAttr(token.attrs.volume_id ?? "")}"` +
    ` data-mention-chapter-id="${escapeHtmlAttr(token.attrs.chapter_id ?? "")}"` +
    ` data-mention-note-id="${escapeHtmlAttr(token.attrs.note_id ?? "")}"` +
    ` data-mention-note-category-id="${escapeHtmlAttr(token.attrs.note_category_id ?? "")}"` +
    ` data-mention-world-info-entry-id="${escapeHtmlAttr(token.attrs.world_info_entry_id ?? "")}"` +
    ` data-mention-character-id="${escapeHtmlAttr(token.attrs.character_id ?? "")}"` +
    ` data-mention-line-start="${escapeHtmlAttr(token.attrs.line_start ?? "")}"` +
    ` data-mention-line-end="${escapeHtmlAttr(token.attrs.line_end ?? "")}"` +
    `></span>`
  );
}

export function mentionTextToHtml(text: string): string {
  if (!text) return "";

  const segments = parseMentionText(text);
  const paragraphs: string[] = [""];

  const appendText = (value: string) => {
    const parts = value.split("\n");
    parts.forEach((part, index) => {
      paragraphs[paragraphs.length - 1] += escapeHtml(part);
      if (index < parts.length - 1) {
        paragraphs.push("");
      }
    });
  };

  segments.forEach((segment) => {
    if (typeof segment === "string") {
      appendText(segment);
      return;
    }
    paragraphs[paragraphs.length - 1] += buildMentionHtml(segment);
  });

  return paragraphs.map((paragraph) => `<p>${paragraph}</p>`).join("");
}

export function serializeMentionToken(token: AssistantMentionToken): string {
  return token.raw;
}

function stripLineRangeSuffix(label: string): string {
  return label.replace(/\s+L?\d+(?:-\d+)?$/u, "").trim();
}

function getLineRangeDisplayLabel(token: AssistantMentionToken): string | null {
  const startLine = token.attrs.line_start?.trim();
  const endLine = token.attrs.line_end?.trim();
  if (!startLine || !endLine) return null;

  const rangeLabel = `L${startLine}-${endLine}`;
  const rawLabel = token.attrs.label?.trim() ?? "";
  const baseLabel = stripLineRangeSuffix(rawLabel);

  if (baseLabel) return `${baseLabel} ${rangeLabel}`;

  const chapterLabel = token.attrs.chapter_id?.trim();
  if (chapterLabel) return `${chapterLabel} ${rangeLabel}`;

  return rangeLabel;
}

export function getMentionDisplayLabel(token: AssistantMentionToken): string {
  if (isExpandedMention(token)) {
    const lineRangeLabel = getLineRangeDisplayLabel(token);
    if (lineRangeLabel) return lineRangeLabel;
  }

  return (
    token.attrs.label?.trim() ||
    token.attrs.chapter_id?.trim() ||
    token.attrs.note_id?.trim() ||
    token.attrs.volume_id?.trim() ||
    token.attrs.note_category_id?.trim() ||
    token.attrs.world_info_entry_id?.trim() ||
    token.attrs.character_id?.trim() ||
    token.kind
  );
}

export function getMentionNavigationTarget(token: AssistantMentionToken): {
  chapterId?: string;
  noteId?: string;
  title: string;
} | null {
  if (token.kind === "volume") return null;
  if (token.kind === "note_category") return null;
  if (token.kind === "world_info_entry") return null;
  if (token.kind === "character") return null;

  if (token.kind === "note") {
    const noteId = token.attrs.note_id?.trim();
    if (!noteId) return null;
    return {
      noteId,
      title: token.attrs.label?.trim() || noteId,
    };
  }

  const chapterId = token.attrs.chapter_id?.trim();
  if (!chapterId) return null;

  return {
    chapterId,
    title: stripLineRangeSuffix(token.attrs.label?.trim() ?? "") || chapterId,
  };
}

export function buildVolumeMentionTag({
  volumeId,
  label,
}: {
  volumeId: string;
  label: string;
}): string {
  return `<of-mention volume_id="${escapeMentionAttribute(volumeId)}" label="${escapeMentionAttribute(label)}" />`;
}

export function buildChapterMentionTag({
  chapterId,
  label,
}: {
  chapterId: string;
  label: string;
}): string {
  return `<of-mention chapter_id="${escapeMentionAttribute(chapterId)}" label="${escapeMentionAttribute(label)}" />`;
}

export function buildNoteMentionTag({ noteId, label }: { noteId: string; label: string }): string {
  return `<of-mention note_id="${escapeMentionAttribute(noteId)}" label="${escapeMentionAttribute(label)}" />`;
}

export function buildNoteCategoryMentionTag({
  categoryId,
  label,
}: {
  categoryId: string;
  label: string;
}): string {
  return `<of-mention note_category_id="${escapeMentionAttribute(categoryId)}" label="${escapeMentionAttribute(label)}" />`;
}

export function buildWorldInfoEntryMentionTag({
  worldInfoEntryId,
  label,
}: {
  worldInfoEntryId: string;
  label: string;
}): string {
  return `<of-mention world_info_entry_id="${escapeMentionAttribute(worldInfoEntryId)}" label="${escapeMentionAttribute(label)}" />`;
}

export function buildCharacterMentionTag({
  characterId,
  label,
}: {
  characterId: string;
  label: string;
}): string {
  return `<of-mention character_id="${escapeMentionAttribute(characterId)}" label="${escapeMentionAttribute(label)}" />`;
}

export function buildLineRangeMentionTag({
  chapterId,
  startLine,
  endLine,
  label,
  snapshotText,
}: {
  chapterId: string;
  startLine: number;
  endLine: number;
  label: string;
  snapshotText: string;
}): string {
  return (
    `<of-mention chapter_id="${escapeMentionAttribute(chapterId)}" line_start="${startLine}" ` +
    `line_end="${endLine}" label="${escapeMentionAttribute(label)}">${escapeMentionEntities(snapshotText)}</of-mention>`
  );
}

export function appendMentionMarkup(currentText: string, mentionMarkup: string): string {
  if (!currentText.trim()) return mentionMarkup;
  if (/\s$/.test(currentText)) return `${currentText}${mentionMarkup}`;
  return `${currentText} ${mentionMarkup}`;
}

export function filterMentionCandidates(
  candidates: AssistantMentionCandidate[],
  query: string,
): AssistantMentionCandidate[] {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return [];

  return candidates.filter(
    (candidate) =>
      candidate.title.toLowerCase().includes(normalizedQuery) ||
      pinyinMatch(candidate.title, normalizedQuery),
  );
}

export function findActiveMentionQuery(textBeforeCursor: string): {
  query: string;
  replaceLength: number;
} | null {
  const match = textBeforeCursor.match(/(?:^|\s)@([^\s@]*)$/);
  if (!match) return null;
  const query = match[1] ?? "";
  return {
    query,
    replaceLength: query.length + 1,
  };
}
