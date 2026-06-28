import type { AgentMessage } from "@/lib/agent.types";

import { getSubagentTargetLabel } from "./subagent-tool-message-utils";

export function getNotifySubagentTitle(): string {
  return "已通知";
}

export function getNotifySubagentDetail(message: AgentMessage): string {
  return getSubagentTargetLabel(message);
}
