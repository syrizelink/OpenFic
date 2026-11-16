import type { PlanStatus } from "../shared/tool-message-utils";

const PLAN_TODO_MARKERS: Record<PlanStatus, string> = {
  pending: "[ ]",
  in_progress: "[*]",
  completed: "[✓]",
};

export function getPlanTodoMarker(status: PlanStatus): string {
  return PLAN_TODO_MARKERS[status];
}
