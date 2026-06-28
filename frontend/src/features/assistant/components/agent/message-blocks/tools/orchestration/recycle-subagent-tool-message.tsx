import type { AgentMessage } from "@/lib/agent.types";

import { getSubagentTargetLabel } from "./subagent-tool-message-utils";

export function getRecycleSubagentTitle(): string {
  return "已回收";
}

export function getRecycleSubagentDetail(message: AgentMessage): string {
  return getSubagentTargetLabel(message);
}
