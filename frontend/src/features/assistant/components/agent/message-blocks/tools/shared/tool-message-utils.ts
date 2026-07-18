import { formatChapterDisplayName } from "@/features/assistant/lib/chapter-tool-preview";
import i18n from "@/i18n";
import type {
  AgentMessage,
  ClarificationQuestion,
  OutlineBeatData,
  OutlineData,
} from "@/lib/agent.types";

export type TodoStatus = "pending" | "running" | "completed";

export interface TodoListItem {
  content: string;
  detail?: string;
  status?: TodoStatus;
}

export interface ChapterPayload {
  id?: string;
  title?: string;
  content?: string;
  chapter_id?: string;
  order?: number;
  word_count?: number;
  volume_id?: string;
}

export interface VolumePayload {
  order?: number;
  title?: string;
  description?: string;
  chapter_count?: number;
}

export interface NotePayload {
  id?: string;
  title?: string;
  content?: string;
  category_id?: string | null;
}

export interface NoteItemPayload {
  type: "category" | "note";
  id: string;
  title: string;
}

export interface ChapterSummaryPayload {
  order?: number;
  title?: string;
  summary?: string;
}

export interface RangeSummaryPayload {
  start_order?: number;
  end_order?: number;
  summary?: string;
}

export interface WorldInfoEntryPayload {
  title?: string;
  content?: string;
  uid?: number;
  order?: number;
}

export interface CharacterPayload {
  name?: string;
  description?: string;
}

export interface OutlineBeatRow {
  content: string;
  tone?: string;
  note?: string;
}

export interface AskUserQuestionAnswerPair {
  question: string;
  description?: string;
  answer: string;
}

export type PlanStatus = "pending" | "in_progress" | "completed";
export type PlanPriority = "low" | "medium" | "high";

export interface PlanTodoPayload {
  content: string;
  status: PlanStatus;
  priority: PlanPriority;
}

export type ToolMessageContentMode = "expandable" | "static" | "hidden";

export interface ToolMessageVisibilityState {
  canExpand: boolean;
  showStaticContent: boolean;
  showErrorIndicator: boolean;
  showDetail: boolean;
  showExpandButton: boolean;
}

export const TODO_STATUS_LABELS: Record<TodoStatus, string> = {
  pending: i18n.t("assistant.tools.todoStatus.pending"),
  running: i18n.t("assistant.tools.todoStatus.running"),
  completed: i18n.t("assistant.tools.todoStatus.completed"),
};

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

export function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function asBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

export function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
}

export function asNumberArray(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item === "number" && Number.isFinite(item)) return [item];
    if (typeof item === "string" && item.trim()) {
      const parsed = Number(item);
      return Number.isFinite(parsed) ? [parsed] : [];
    }
    return [];
  });
}

export function asRecordArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

export function asTodoStatus(value: unknown): TodoStatus | undefined {
  return value === "pending" || value === "running" || value === "completed" ? value : undefined;
}

export function asPlanStatus(value: unknown): PlanStatus | undefined {
  return value === "pending" || value === "in_progress" || value === "completed"
    ? value
    : undefined;
}

export function formatValue(value: unknown): string | undefined {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return undefined;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function asClarificationQuestions(value: unknown): ClarificationQuestion[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item): ClarificationQuestion | null => {
      if (typeof item === "string") return { title: item, options: [] };
      if (!isRecord(item)) return null;
      const title = asString(item.title);
      if (!title) return null;
      const options = Array.isArray(item.options)
        ? item.options
            .filter(isRecord)
            .map((option) => ({
              label: asString(option.label) ?? "",
              description: asString(option.description),
            }))
            .filter((option) => option.label)
        : [];
      return {
        title,
        description: asString(item.description),
        options,
      };
    })
    .filter((question): question is ClarificationQuestion => Boolean(question));
}

export function asPartialBeats(value: unknown): OutlineBeatData[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isRecord)
    .map((beat) => ({
      content: asString(beat.content) ?? "",
      tone: asString(beat.tone),
      note: asString(beat.note),
    }))
    .filter((beat) => beat.content || beat.tone || beat.note);
}

export function getToolData(message: AgentMessage): Record<string, unknown> {
  const resultData = message.toolResult?.data;
  if (isRecord(resultData)) return resultData;
  if (isRecord(message.toolResult)) return message.toolResult;
  if (message.partialToolArgs) return message.partialToolArgs;
  if (message.toolArgs) return message.toolArgs;
  return message.payload ?? {};
}

export function getToolResultData(message: AgentMessage): unknown {
  return message.toolResult?.data ?? message.toolResult;
}

export function getNestedRecord(
  data: Record<string, unknown>,
  key: string,
): Record<string, unknown> | null {
  const nested = data[key];
  return isRecord(nested) ? nested : null;
}

export function getStreamingData(message: AgentMessage): Record<string, unknown> {
  if (message.partialToolArgs) return message.partialToolArgs;
  if (message.toolArgs) return message.toolArgs;
  return getToolData(message);
}

export function getOutlineData(message: AgentMessage): Partial<OutlineData> {
  const streamingData = getStreamingData(message);
  return (
    message.outlineData ??
    getNestedRecord(streamingData, "outline") ??
    (streamingData as Partial<OutlineData>)
  );
}

export function getOutlineBeatRows(message: AgentMessage): OutlineBeatRow[] {
  return asPartialBeats(getOutlineData(message).beats).map((beat, index) => ({
    content: beat.content || i18n.t("assistant.tools.outlineBeat", { index: index + 1 }),
    tone: beat.tone,
    note: beat.note,
  }));
}

export function getOutlineItems(message: AgentMessage): TodoListItem[] {
  return getOutlineBeatRows(message).map((beat) => {
    const detail = [
      beat.tone ? i18n.t("assistant.tools.outlineTone", { tone: beat.tone }) : undefined,
      beat.note ? i18n.t("assistant.tools.outlineNote", { note: beat.note }) : undefined,
    ]
      .filter(Boolean)
      .join(" · ");
    return {
      content: beat.content,
      detail: detail || undefined,
    };
  });
}

function normalizeAskUserAnswerValue(value: unknown): string | undefined {
  if (typeof value === "string" && value.trim()) return value;
  return formatValue(value);
}

function getAskUserAnswerRecords(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) return value.filter(isRecord);
  if (isRecord(value) && Array.isArray(value.answers)) {
    return value.answers.filter(isRecord);
  }
  if (
    isRecord(value) &&
    (value.answer !== undefined || value.label !== undefined || value.question !== undefined)
  ) {
    return [value];
  }
  return [];
}

function parseClarificationAnswerText(value: string): AskUserQuestionAnswerPair[] {
  const lines = value.split(/\r?\n/);
  const pairs: AskUserQuestionAnswerPair[] = [];
  let currentTitle: string | null = null;
  let currentAnswerLines: string[] = [];

  const pushCurrent = () => {
    if (!currentTitle) return;
    const answer = currentAnswerLines.join("\n").trim();
    if (answer) {
      pairs.push({
        question: currentTitle,
        answer,
      });
    }
  };

  for (const line of lines) {
    const headingMatch = line.match(/^\s*(\d+)\.\s+(.+?)\s*$/);
    if (headingMatch) {
      pushCurrent();
      currentTitle = headingMatch[2] ?? null;
      currentAnswerLines = [];
      continue;
    }

    if (!currentTitle) continue;
    currentAnswerLines.push(line);
  }

  pushCurrent();
  return pairs;
}

export function getAskUserQuestionAnswerPairs(message: AgentMessage): AskUserQuestionAnswerPair[] {
  const questions = asClarificationQuestions(getStreamingData(message).questions);
  const resultData = getToolResultData(message);

  if (isRecord(resultData) && typeof resultData.answer === "string") {
    const parsedPairs = parseClarificationAnswerText(resultData.answer);
    if (parsedPairs.length > 0) {
      return parsedPairs.map((pair, index) => ({
        ...pair,
        description:
          questions.find((question) => question.title === pair.question)?.description ??
          questions[index]?.description,
      }));
    }
  }

  const answerRecords = getAskUserAnswerRecords(resultData);

  if (answerRecords.length > 0) {
    return answerRecords.flatMap((record, index) => {
      const answer = normalizeAskUserAnswerValue(record.answer);
      const questionTitle =
        asString(record.question) ??
        asString(record.title) ??
        asString(record.label) ??
        questions[index]?.title;
      if (!questionTitle || !answer) return [];
      const matchingQuestion =
        questions.find((question) => question.title === questionTitle) ?? questions[index];
      return [
        {
          question: questionTitle,
          description: matchingQuestion?.description,
          answer,
        },
      ];
    });
  }

  if (typeof resultData === "string") {
    const parsedPairs = parseClarificationAnswerText(resultData);
    if (parsedPairs.length > 0) {
      return parsedPairs.map((pair, index) => ({
        ...pair,
        description:
          questions.find((question) => question.title === pair.question)?.description ??
          questions[index]?.description,
      }));
    }
  }

  if (isRecord(resultData)) {
    const answer = normalizeAskUserAnswerValue(resultData.answer);
    const questionTitle =
      questions[0]?.title ?? asString(resultData.question) ?? asString(resultData.title);
    if (questionTitle && answer) {
      return [
        {
          question: questionTitle,
          description: questions[0]?.description,
          answer,
        },
      ];
    }
  }

  return [];
}

export function getAskUserTitle(message: AgentMessage): string {
  return message.status === "completed"
    ? i18n.t("assistant.tools.asked")
    : i18n.t("assistant.tools.asking");
}

export function getAskUserQuestionCount(message: AgentMessage): number {
  const questions = asClarificationQuestions(getStreamingData(message).questions);
  if (questions.length > 0) return questions.length;
  return getAskUserQuestionAnswerPairs(message).length;
}

export function getAskUserQuestionCountDetail(message: AgentMessage): string {
  return i18n.t("assistant.tools.questionCount", { count: getAskUserQuestionCount(message) });
}

export function resolveToolMessageVisibilityState(input: {
  message: Pick<AgentMessage, "status" | "isStreaming">;
  contentMode: ToolMessageContentMode;
  hasContent: boolean;
  hasDetail: boolean;
  errorMessage?: string;
}): ToolMessageVisibilityState {
  const isRunning = Boolean(input.message.isStreaming || input.message.status === "running");
  const hasError = Boolean(input.errorMessage);
  const canExpand =
    !hasError && input.contentMode === "expandable" && !isRunning && input.hasContent;

  return {
    canExpand,
    showStaticContent: !hasError && input.hasContent && input.contentMode === "static",
    showErrorIndicator: hasError,
    showDetail: !hasError && input.hasDetail,
    showExpandButton: !hasError && canExpand,
  };
}

function toPlanTodoPayload(value: unknown): PlanTodoPayload | null {
  if (!isRecord(value)) return null;
  const content = asString(value.content);
  const priority = value.priority;
  if (!content || (priority !== "low" && priority !== "medium" && priority !== "high")) return null;
  return {
    content,
    status: asPlanStatus(value.status) ?? "pending",
    priority,
  };
}

export function getPlanTodos(message: AgentMessage): PlanTodoPayload[] {
  const resultData = getToolResultData(message);
  if (isRecord(resultData) && isRecord(resultData.plan)) {
    return asRecordArray(resultData.plan.todos)
      .map(toPlanTodoPayload)
      .filter((todo): todo is PlanTodoPayload => Boolean(todo));
  }
  const data = getStreamingData(message);
  return asRecordArray(data.todos)
    .map(toPlanTodoPayload)
    .filter((todo): todo is PlanTodoPayload => Boolean(todo));
}

export function formatOutlineDetail(message: AgentMessage): string | undefined {
  const count = getOutlineItems(message).length;
  return count > 0 ? i18n.t("assistant.tools.outlineCount", { count }) : undefined;
}

export function getChapterPayload(message: AgentMessage): ChapterPayload {
  const data = getToolData(message);
  const chapterData = isRecord(data.chapter) ? data.chapter : data;
  const toolArgs = message.toolArgs ?? {};
  const id =
    typeof chapterData.id === "string"
      ? chapterData.id
      : typeof chapterData.chapter_id === "string"
        ? chapterData.chapter_id
        : typeof toolArgs.chapter_id === "string"
          ? toolArgs.chapter_id
          : undefined;
  const chapterRef = isRecord(toolArgs.chapter_ref) ? toolArgs.chapter_ref : null;
  const chapterRefTitle = chapterRef?.type === "title" ? asString(chapterRef.value) : undefined;
  return {
    id,
    title:
      typeof chapterData.title === "string"
        ? chapterData.title
        : typeof toolArgs.title === "string"
          ? toolArgs.title
          : typeof toolArgs.new_title === "string"
            ? toolArgs.new_title
            : chapterRefTitle,
    content:
      typeof chapterData.content === "string"
        ? chapterData.content
        : typeof toolArgs.content === "string"
          ? toolArgs.content
          : undefined,
    chapter_id: id,
    order: asNumber(chapterData.order),
    word_count: asNumber(chapterData.word_count),
    volume_id: asString(chapterData.volume_id),
  };
}

export function getChapterList(message: AgentMessage): Record<string, unknown>[] {
  const resultData = getToolResultData(message);
  if (Array.isArray(resultData)) return resultData.filter(isRecord);
  if (isRecord(resultData) && Array.isArray(resultData.chapters)) {
    return resultData.chapters.filter(isRecord);
  }
  const data = getToolData(message);
  if (Array.isArray(data.chapters)) return data.chapters.filter(isRecord);
  return [];
}

function toVolumePayload(value: Record<string, unknown>): VolumePayload {
  return {
    order: asNumber(value.order),
    title: asString(value.title),
    description: asString(value.description),
    chapter_count: asNumber(value.chapter_count),
  };
}

export function getVolumePayload(message: AgentMessage): VolumePayload | null {
  const resultData = getToolResultData(message);
  if (isRecord(resultData) && isRecord(resultData.volume)) {
    return toVolumePayload(resultData.volume);
  }
  const data = getToolData(message);
  if (isRecord(data.volume)) return toVolumePayload(data.volume);
  return null;
}

export function getVolumeList(message: AgentMessage): VolumePayload[] {
  const resultData = getToolResultData(message);
  if (Array.isArray(resultData)) return resultData.filter(isRecord).map(toVolumePayload);
  if (isRecord(resultData) && Array.isArray(resultData.volumes)) {
    return resultData.volumes.filter(isRecord).map(toVolumePayload);
  }
  const data = getToolData(message);
  if (Array.isArray(data.volumes)) return data.volumes.filter(isRecord).map(toVolumePayload);
  return [];
}

export function getNotePayload(message: AgentMessage): NotePayload {
  const resultData = getToolResultData(message);
  if (isRecord(resultData) && isRecord(resultData.note)) {
    const note = resultData.note;
    return {
      id: asString(note.id),
      title: asString(note.title),
      content: asString(note.content),
      category_id: asString(note.category_id) ?? null,
    };
  }
  if (isRecord(resultData) && asString(resultData.title)) {
    return {
      id: asString(resultData.id),
      title: asString(resultData.title),
      content: asString(resultData.content),
    };
  }
  const streamingData = getStreamingData(message);
  const toolArgs = message.toolArgs ?? {};
  const noteRef = isRecord(toolArgs.note_ref) ? toolArgs.note_ref : null;
  return {
    id: asString(noteRef?.id),
    title: asString(streamingData.title) ?? asString(noteRef?.title),
    content: asString(streamingData.content),
  };
}

export function getNoteItemList(message: AgentMessage): NoteItemPayload[] {
  const resultData = getToolResultData(message);
  if (!isRecord(resultData) || !Array.isArray(resultData.items)) return [];
  return resultData.items
    .filter(isRecord)
    .map(
      (item): NoteItemPayload => ({
        type: item.type === "category" ? "category" : "note",
        id: asString(item.id) ?? "",
        title: asString(item.title) ?? "",
      }),
    )
    .filter((item) => item.id && item.title);
}

export function formatNoteRefLabel(ref: Record<string, unknown> | null): string | undefined {
  if (!ref) return undefined;
  return asString(ref.title) ?? asString(ref.path) ?? asString(ref.id);
}

export function formatCategoryRefLabel(ref: Record<string, unknown> | null): string | undefined {
  if (!ref) return undefined;
  return asString(ref.title) ?? asString(ref.path) ?? asString(ref.id);
}

function toChapterSummaryPayload(value: Record<string, unknown>): ChapterSummaryPayload {
  return {
    order: asNumber(value.order),
    title: asString(value.title),
    summary: asString(value.summary),
  };
}

export function getChapterSummaryList(message: AgentMessage): ChapterSummaryPayload[] {
  const resultData = getToolResultData(message);
  if (isRecord(resultData) && Array.isArray(resultData.summaries)) {
    return resultData.summaries.filter(isRecord).map(toChapterSummaryPayload);
  }
  const data = getToolData(message);
  if (Array.isArray(data.summaries))
    return data.summaries.filter(isRecord).map(toChapterSummaryPayload);
  return [];
}

function toRangeSummaryPayload(value: Record<string, unknown>): RangeSummaryPayload {
  return {
    start_order: asNumber(value.start_order),
    end_order: asNumber(value.end_order),
    summary: asString(value.summary),
  };
}

export function getRangeSummaryList(message: AgentMessage): RangeSummaryPayload[] {
  const resultData = getToolResultData(message);
  if (isRecord(resultData) && Array.isArray(resultData.summaries)) {
    return resultData.summaries.filter(isRecord).map(toRangeSummaryPayload);
  }
  const data = getToolData(message);
  if (Array.isArray(data.summaries))
    return data.summaries.filter(isRecord).map(toRangeSummaryPayload);
  return [];
}

export function getWorldEntryPayload(message: AgentMessage): WorldInfoEntryPayload {
  const resultData = getToolResultData(message);
  const data = getToolData(message);
  const entryData =
    isRecord(resultData) && isRecord(resultData.world_entry) ? resultData.world_entry : data;
  const diff =
    isRecord(resultData) && isRecord(resultData.world_entry_diff)
      ? resultData.world_entry_diff
      : null;
  return {
    title:
      asString(entryData.title) ??
      asString(entryData.name) ??
      asString(diff?.entry_title) ??
      asString(data.title) ??
      asString(data.new_title),
    content: asString(entryData.content) ?? asString(data.content) ?? asString(data.new_content),
    uid: asNumber(entryData.uid),
    order: asNumber(entryData.order),
  };
}

export function getWorldEntryList(message: AgentMessage): WorldInfoEntryPayload[] {
  const resultData = getToolResultData(message);
  const entries =
    isRecord(resultData) && Array.isArray(resultData.entries) ? resultData.entries : [];
  return entries
    .filter(isRecord)
    .map((entry) => ({
      title: asString(entry.title) ?? asString(entry.name),
      uid: asNumber(entry.uid),
      order: asNumber(entry.order),
    }))
    .filter((entry) => entry.title);
}

export function getCharacterPayload(message: AgentMessage): CharacterPayload {
  const resultData = getToolResultData(message);
  const data = getToolData(message);
  const characterData =
    isRecord(resultData) && isRecord(resultData.character) ? resultData.character : data;
  const diff =
    isRecord(resultData) && isRecord(resultData.character_diff) ? resultData.character_diff : null;
  return {
    name:
      asString(characterData.name) ??
      asString(diff?.character_name) ??
      asString(data.name) ??
      asString(data.new_name),
    description:
      asString(characterData.description) ??
      asString(data.description) ??
      asString(data.new_description),
  };
}

export function getCharacterList(message: AgentMessage): CharacterPayload[] {
  const resultData = getToolResultData(message);
  const characters =
    isRecord(resultData) && Array.isArray(resultData.characters) ? resultData.characters : [];
  return characters
    .filter(isRecord)
    .map((character) => ({
      name: asString(character.name),
      description: asString(character.description),
    }))
    .filter((character) => character.name);
}

export function getToolRef(message: AgentMessage, key: string): Record<string, unknown> | null {
  const data = getStreamingData(message);
  const toolArgs = message.toolArgs ?? {};
  const dataValue = data[key];
  if (isRecord(dataValue)) return dataValue;
  const argValue = toolArgs[key];
  return isRecord(argValue) ? argValue : null;
}

function formatReferenceLabel(
  ref: Record<string, unknown> | null,
  orderedLabel: string,
): string | undefined {
  if (!ref) return undefined;
  const value = ref.value;
  const type = asString(ref.type);
  if (type === "order") {
    if (typeof value === "number" && Number.isFinite(value))
      return i18n.t("assistant.tools.orderedReference", { value, unit: orderedLabel });
    if (typeof value === "string" && value.trim())
      return i18n.t("assistant.tools.orderedReference", {
        value: value.trim(),
        unit: orderedLabel,
      });
  }
  return asString(value);
}

export function formatVolumeRefLabel(ref: Record<string, unknown> | null): string | undefined {
  return formatReferenceLabel(ref, i18n.t("assistant.tools.volumeUnit"));
}

export function formatChapterRefLabel(ref: Record<string, unknown> | null): string | undefined {
  return formatReferenceLabel(ref, i18n.t("assistant.tools.chapterUnit"));
}

export function getReadChapterDetail(message: AgentMessage): string | undefined {
  const chapter = getChapterPayload(message);
  return (
    formatChapterDisplayName({
      order: chapter.order,
      title: chapter.title,
      chapterId: chapter.chapter_id,
    }) ?? formatChapterRefLabel(getToolRef(message, "chapter_ref"))
  );
}

export function formatVolumeDisplayName(volume: VolumePayload): string | undefined {
  const order = volume.order;
  const title = volume.title;
  if (order !== undefined && title)
    return i18n.t("assistant.tools.volumeDisplay", { order, title });
  if (order !== undefined) return i18n.t("assistant.tools.volumeDisplayNoTitle", { order });
  return title;
}

export function formatChapterSummaryQuery(message: AgentMessage): string | undefined {
  const data = getStreamingData(message);
  const offset = asNumber(data.offset);
  const limit = asNumber(data.limit);
  if (offset !== undefined && limit !== undefined) {
    return i18n.t("assistant.tools.pagedRead", { start: offset + 1, end: offset + limit });
  }
  const orders = asNumberArray(data.orders);
  return orders.length > 0
    ? i18n.t("assistant.tools.readByOrders", { orders: orders.join("、") })
    : undefined;
}

export function formatRangeSummaryQuery(message: AgentMessage): string | undefined {
  const data = getStreamingData(message);
  const offset = asNumber(data.offset);
  const limit = asNumber(data.limit);
  if (offset === undefined || limit === undefined) return undefined;
  return i18n.t("assistant.tools.pagedRead", { start: offset + 1, end: offset + limit });
}

export function getToolResultMessage(message: AgentMessage): string | undefined {
  const toolResult = message.toolResult ?? {};
  const resultData = getToolResultData(message);
  return (
    asString(toolResult.message) ??
    (isRecord(resultData) ? asString(resultData.message) : undefined) ??
    asString(toolResult.reason)
  );
}

export function getToolErrorMessage(message: AgentMessage): string | undefined {
  if (message.status !== "error") return undefined;
  const toolResult = message.toolResult ?? {};
  const messageText = asString(toolResult.message);
  const reason = asString(toolResult.reason);
  if (reason === "cancelled") return messageText ?? i18n.t("assistant.tools.cancelled");
  if (reason === "interrupted") return messageText ?? i18n.t("assistant.tools.interrupted");
  if (messageText && reason)
    return `${messageText}\n${i18n.t("assistant.tools.errorReason", { reason })}`;
  return messageText ?? reason ?? message.content;
}
