import type { PlanStatus, ToolMessageContentMode } from "../shared/tool-message-utils";

export interface PlanToolDisplayConfig {
  contentMode: ToolMessageContentMode;
  defaultExpanded: boolean;
}

const PLAN_TOOL_DISPLAY_CONFIG: PlanToolDisplayConfig = {
  contentMode: "expandable",
  defaultExpanded: true,
};

const PLAN_TODO_MARKERS: Record<PlanStatus, string> = {
  pending: "[ ]",
  in_progress: "[*]",
  completed: "[✓]",
};

export function getPlanToolDisplayConfig(): PlanToolDisplayConfig {
  return PLAN_TOOL_DISPLAY_CONFIG;
}

export function getPlanTodoMarker(status: PlanStatus): string {
  return PLAN_TODO_MARKERS[status];
}
