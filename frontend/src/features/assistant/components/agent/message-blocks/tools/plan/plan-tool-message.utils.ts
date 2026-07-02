import type {
  PlanPayload,
  PlanStatus,
  ToolMessageContentMode,
} from "../shared/tool-message-utils";
import i18n from "@/i18n";

export type PlanToolName = "create_plan" | "update_plan" | "get_plan" | "list_plan";
export type PlanToolDetailKind = "topic" | "count";

export interface PlanToolDisplayConfig {
  contentMode: ToolMessageContentMode;
  defaultExpanded: boolean;
  detailKind: PlanToolDetailKind;
}

export interface PlanChecklistItem {
  id: string;
  title: string;
  content: string;
  status: PlanStatus;
  marker: string;
}

export interface PlanDisplayTodoRow {
  kind: "todo";
  id: string;
  item: PlanChecklistItem;
}

export interface PlanDisplaySummaryRow {
  kind: "summary";
  id: string;
  label: string;
}

export type PlanDisplayRow = PlanDisplayTodoRow | PlanDisplaySummaryRow;

const PLAN_TOOL_DISPLAY_CONFIG: Record<PlanToolName, PlanToolDisplayConfig> = {
  create_plan: {
    contentMode: "expandable",
    defaultExpanded: true,
    detailKind: "topic",
  },
  update_plan: {
    contentMode: "expandable",
    defaultExpanded: true,
    detailKind: "topic",
  },
  get_plan: {
    contentMode: "hidden",
    defaultExpanded: false,
    detailKind: "topic",
  },
  list_plan: {
    contentMode: "hidden",
    defaultExpanded: false,
    detailKind: "count",
  },
};

const PLAN_TODO_MARKERS: Record<PlanStatus, string> = {
  pending: "[ ]",
  in_progress: "[*]",
  completed: "[✓]",
};

export function getPlanToolDisplayConfig(toolName: PlanToolName): PlanToolDisplayConfig {
  return PLAN_TOOL_DISPLAY_CONFIG[toolName];
}

export function getPlanTodoMarker(status: PlanStatus): string {
  return PLAN_TODO_MARKERS[status];
}

export function getPlanCardTopic(plan: PlanPayload): string | undefined {
  return plan.topic.trim() || undefined;
}

export function buildPlanChecklistItems(plan: PlanPayload): PlanChecklistItem[] {
  return plan.todos.map((todo, index) => ({
    id: todo.id ?? `plan-todo-${index}`,
    title: todo.title,
    content: todo.content,
    status: todo.status,
    marker: getPlanTodoMarker(todo.status),
  }));
}

export function getPlanTodoToggleLabel(expanded: boolean): string {
  return expanded ? i18n.t("assistant.tools.collapsePlanSteps") : i18n.t("assistant.tools.expandPlanSteps");
}

export function getPlanSummaryLabel(statuses: PlanStatus[]): string {
  const count = statuses.length;
  if (count === 0) return "";

  const allCompleted = statuses.every((status) => status === "completed");
  const allPending = statuses.every((status) => status === "pending");

  if (allCompleted) return i18n.t("assistant.tools.completedSteps", { count });
  if (allPending) return i18n.t("assistant.tools.pendingSteps", { count });
  return i18n.t("assistant.tools.remainingSteps", { count });
}

export function buildUpdatePlanDisplayRows(
  plan: PlanPayload,
  maxVisibleTodos = 8
): PlanDisplayRow[] {
  const checklistItems = buildPlanChecklistItems(plan);
  if (checklistItems.length === 0) return [];

  const firstInProgressIndex = checklistItems.findIndex((item) => item.status === "in_progress");
  const topItem =
    firstInProgressIndex >= 0 ? checklistItems[firstInProgressIndex] : undefined;
  const itemsBeforeTop =
    firstInProgressIndex >= 0 ? checklistItems.slice(0, firstInProgressIndex) : [];
  const itemsAfterTop =
    firstInProgressIndex >= 0 ? checklistItems.slice(firstInProgressIndex + 1) : checklistItems;
  const completedBeforeTop = itemsBeforeTop.filter((item) => item.status === "completed");
  const nonCompletedBeforeTop = itemsBeforeTop.filter((item) => item.status !== "completed");
  const orderedItems = topItem
    ? [topItem, ...nonCompletedBeforeTop, ...itemsAfterTop]
    : checklistItems.slice();
  const visibleItems = orderedItems.slice(0, maxVisibleTodos);
  const omittedItems = orderedItems.slice(maxVisibleTodos);
  const rows: PlanDisplayRow[] = [];

  if (completedBeforeTop.length > 0) {
    rows.push({
      kind: "summary",
      id: `plan-summary-completed-${completedBeforeTop.length}`,
      label: getPlanSummaryLabel(completedBeforeTop.map((item) => item.status)),
    });
  }

  if (topItem) {
    rows.push({
      kind: "todo",
      id: topItem.id,
      item: topItem,
    });
  }

  rows.push(
    ...visibleItems.slice(topItem ? 1 : 0).map((item) => ({
      kind: "todo" as const,
      id: item.id,
      item,
    }))
  );

  if (omittedItems.length > 0) {
    rows.push({
      kind: "summary",
      id: `plan-summary-tail-${omittedItems.length}`,
      label: getPlanSummaryLabel(omittedItems.map((item) => item.status)),
    });
  }

  return rows;
}
