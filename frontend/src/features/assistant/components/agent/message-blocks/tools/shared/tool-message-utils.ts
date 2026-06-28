import type {
  AgentMessage,
  ClarificationQuestion,
  OutlineBeatData,
  OutlineData,
} from "@/lib/agent.types";
import { formatChapterDisplayName } from "../../../../../lib/chapter-tool-preview";

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
  name: string;
  content: string;
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

export interface PlanDependencyPayload {
  todo_id?: string;
  plan_id?: string;
  todo_title?: string;
  todo_content?: string;
}

export interface PlanTodoPayload {
  id?: string;
  title: string;
  content: string;
  status: PlanStatus;
}

export interface PlanPayload {
  id?: string;
  topic: string;
  description: string;
  status: PlanStatus;
  parent_dependency: PlanDependencyPayload | null;
  todos: PlanTodoPayload[];
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
  pending: "未完成",
  running: "进行中",
  completed: "已完成",
};

export const PLAN_STATUS_LABELS: Record<PlanStatus, string> = {
  pending: "未开始",
  in_progress: "进行中",
  completed: "已完成",
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
  return value === "pending" || value === "in_progress" || value === "completed" ? value : undefined;
}

export function getPlanStatusLabel(status: PlanStatus | undefined): string | undefined {
  return status ? PLAN_STATUS_LABELS[status] : undefined;
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
  key: string
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
    content: beat.content || `情节点 ${index + 1}`,
    tone: beat.tone,
    note: beat.note,
  }));
}

export function getOutlineItems(message: AgentMessage): TodoListItem[] {
  return getOutlineBeatRows(message).map((beat) => {
    const detail = [
      beat.tone ? `情绪基调：${beat.tone}` : undefined,
      beat.note ? `备注：${beat.note}` : undefined,
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
  if (isRecord(value) && (value.answer !== undefined || value.label !== undefined || value.question !== undefined)) {
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
    return answerRecords
      .flatMap((record, index) => {
        const answer = normalizeAskUserAnswerValue(record.answer);
        const questionTitle =
          asString(record.question) ??
          asString(record.title) ??
          asString(record.label) ??
          questions[index]?.title;
        if (!questionTitle || !answer) return [];
        const matchingQuestion = questions.find((question) => question.title === questionTitle) ?? questions[index];
        return [{
          question: questionTitle,
          description: matchingQuestion?.description,
          answer,
        }];
      });
  }

  if (typeof resultData === "string") {
    const parsedPairs = parseClarificationAnswerText(resultData);
    if (parsedPairs.length > 0) {
      return parsedPairs.map((pair, index) => ({
        ...pair,
        description: questions.find((question) => question.title === pair.question)?.description ?? questions[index]?.description,
      }));
    }
  }

  if (isRecord(resultData)) {
    const answer = normalizeAskUserAnswerValue(resultData.answer);
    const questionTitle = questions[0]?.title ?? asString(resultData.question) ?? asString(resultData.title);
    if (questionTitle && answer) {
      return [{
        question: questionTitle,
        description: questions[0]?.description,
        answer,
      }];
    }
  }

  return [];
}

export function getAskUserTitle(message: AgentMessage): string {
  return message.status === "completed" ? "已询问" : "询问";
}

export function getAskUserQuestionCount(message: AgentMessage): number {
  const questions = asClarificationQuestions(getStreamingData(message).questions);
  if (questions.length > 0) return questions.length;
  return getAskUserQuestionAnswerPairs(message).length;
}

export function getAskUserQuestionCountDetail(message: AgentMessage): string {
  return `${getAskUserQuestionCount(message)} 个问题`;
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

function toPlanDependencyPayload(value: Record<string, unknown>): PlanDependencyPayload {
  return {
    todo_id: asString(value.todo_id),
    plan_id: asString(value.plan_id),
    todo_title: asString(value.todo_title),
    todo_content: asString(value.todo_content),
  };
}

function toPlanTodoPayload(value: unknown, index: number): PlanTodoPayload | null {
  if (!isRecord(value)) return null;
  const title = asString(value.title);
  const content = asString(value.content);
  if (!title || !content) return null;
  return {
    id: asString(value.id) ?? `plan-todo-${index}`,
    title,
    content,
    status: asPlanStatus(value.status) ?? "pending",
  };
}

function toPlanPayload(value: Record<string, unknown>): PlanPayload {
  return {
    id: asString(value.id),
    topic: asString(value.topic) ?? "",
    description: asString(value.description) ?? "",
    status: asPlanStatus(value.status) ?? "pending",
    parent_dependency: isRecord(value.parent_dependency)
      ? toPlanDependencyPayload(value.parent_dependency)
      : null,
    todos: asRecordArray(value.todos)
      .map((todo, index) => toPlanTodoPayload(todo, index))
      .filter((todo): todo is PlanTodoPayload => Boolean(todo)),
  };
}

function getDraftPlanPayload(message: AgentMessage): PlanPayload | null {
  const data = getStreamingData(message);
  const topic = asString(data.topic);
  const description = asString(data.description);
  const todos = Array.isArray(data.todos)
    ? data.todos.flatMap((todo, index) => {
        if (!isRecord(todo)) return [];
        const title = asString(todo.title);
        const content = asString(todo.content);
        if (!title || !content) return [];
        return [{
          id: `draft-plan-todo-${index}`,
          title,
          content,
          status: "pending" as const,
        }];
      })
    : [];
  if (!topic && !description && todos.length === 0) return null;
  return {
    id: asString(data.id),
    topic: topic ?? "",
    description: description ?? "",
    status: asPlanStatus(data.status) ?? "pending",
    parent_dependency: null,
    todos,
  };
}

export function getPlanPayload(message: AgentMessage): PlanPayload | null {
  const resultData = getToolResultData(message);
  if (isRecord(resultData) && isRecord(resultData.plan)) {
    return toPlanPayload(resultData.plan);
  }
  const data = getToolData(message);
  if (isRecord(data.plan)) return toPlanPayload(data.plan);
  return getDraftPlanPayload(message);
}

export function getPlanList(message: AgentMessage): PlanPayload[] {
  const resultData = getToolResultData(message);
  if (isRecord(resultData) && Array.isArray(resultData.plans)) {
    return resultData.plans.filter(isRecord).map(toPlanPayload);
  }
  const data = getToolData(message);
  if (Array.isArray(data.plans)) {
    return data.plans.filter(isRecord).map(toPlanPayload);
  }
  return [];
}

export function getPlanCountDetail(message: AgentMessage): string | undefined {
  const count = getPlanList(message).length;
  return `${count} 个计划`;
}

export function getPlanTopicDetail(message: AgentMessage): string | undefined {
  return getPlanPayload(message)?.topic || undefined;
}

export function formatPlanDependencySummary(
  dependency: PlanDependencyPayload | null | undefined
): string | undefined {
  if (!dependency) return undefined;
  const todoLabel = dependency.todo_title ?? dependency.todo_content;
  if (todoLabel && dependency.plan_id) {
    return `依赖 ${dependency.plan_id} · ${todoLabel}`;
  }
  return todoLabel ?? dependency.plan_id ?? dependency.todo_id;
}

export function formatOutlineDetail(message: AgentMessage): string | undefined {
  const count = getOutlineItems(message).length;
  return count > 0 ? `${count} 个情节点` : undefined;
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
    .map((item): NoteItemPayload => ({
      type: item.type === "category" ? "category" : "note",
      id: asString(item.id) ?? "",
      title: asString(item.title) ?? "",
    }))
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
  if (Array.isArray(data.summaries)) return data.summaries.filter(isRecord).map(toChapterSummaryPayload);
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
  if (Array.isArray(data.summaries)) return data.summaries.filter(isRecord).map(toRangeSummaryPayload);
  return [];
}

export function getWorldInfoContent(message: AgentMessage): string | undefined {
  const resultData = getToolResultData(message);
  if (isRecord(resultData) && typeof resultData.content === "string") return resultData.content;
  return asString(getToolData(message).content);
}

export function parseWorldInfoEntries(content: string | undefined): WorldInfoEntryPayload[] {
  if (!content) return [];
  const matches = Array.from(content.matchAll(/<([^>\n]+)>\s*([\s\S]*?)\s*<\/\1>/g));
  return matches
    .map((match) => ({
      name: match[1]?.trim() ?? "",
      content: match[2]?.trim() ?? "",
    }))
    .filter((entry) => entry.name && entry.content);
}

export function getToolRef(
  message: AgentMessage,
  key: string
): Record<string, unknown> | null {
  const data = getStreamingData(message);
  const toolArgs = message.toolArgs ?? {};
  const dataValue = data[key];
  if (isRecord(dataValue)) return dataValue;
  const argValue = toolArgs[key];
  return isRecord(argValue) ? argValue : null;
}

function formatReferenceLabel(
  ref: Record<string, unknown> | null,
  orderedLabel: string
): string | undefined {
  if (!ref) return undefined;
  const value = ref.value;
  const type = asString(ref.type);
  if (type === "order") {
    if (typeof value === "number" && Number.isFinite(value)) return `第${value}${orderedLabel}`;
    if (typeof value === "string" && value.trim()) return `第${value.trim()}${orderedLabel}`;
  }
  return asString(value);
}

export function formatVolumeRefLabel(ref: Record<string, unknown> | null): string | undefined {
  return formatReferenceLabel(ref, "卷");
}

export function formatChapterRefLabel(ref: Record<string, unknown> | null): string | undefined {
  return formatReferenceLabel(ref, "章");
}

export function getReadChapterDetail(message: AgentMessage): string | undefined {
  const chapter = getChapterPayload(message);
  return (
    formatChapterDisplayName({
      order: chapter.order,
      title: chapter.title,
      chapterId: chapter.chapter_id,
    }) ??
    formatChapterRefLabel(getToolRef(message, "chapter_ref"))
  );
}

export function formatVolumeDisplayName(volume: VolumePayload): string | undefined {
  const order = volume.order;
  const title = volume.title;
  if (order !== undefined && title) return `第${order}卷 · ${title}`;
  if (order !== undefined) return `第${order}卷`;
  return title;
}

export function formatChapterSummaryQuery(message: AgentMessage): string | undefined {
  const data = getStreamingData(message);
  const offset = asNumber(data.offset);
  const limit = asNumber(data.limit);
  if (offset !== undefined && limit !== undefined) {
    return `分页读取 ${offset + 1}-${offset + limit}`;
  }
  const orders = asNumberArray(data.orders);
  return orders.length > 0 ? `按章节序号读取：${orders.join("、")}` : undefined;
}

export function formatRangeSummaryQuery(message: AgentMessage): string | undefined {
  const data = getStreamingData(message);
  const offset = asNumber(data.offset);
  const limit = asNumber(data.limit);
  if (offset === undefined || limit === undefined) return undefined;
  return `分页读取 ${offset + 1}-${offset + limit}`;
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
  if (reason === "cancelled") return messageText ?? "用户中止了工具调用";
  if (reason === "interrupted") return messageText ?? "工具调用因连接中断而停止";
  if (messageText && reason) return `${messageText}\n原因：${reason}`;
  return messageText ?? reason ?? message.content;
}
