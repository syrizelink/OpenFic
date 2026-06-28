import type { AgentMessage } from "@/lib/agent.types";

import { getSubagentTargetLabel } from "./subagent-tool-message-utils";

export function getSubagentDispatchTitle(message: AgentMessage): string {
  void message;
  return "已委派";
}

export function getSubagentDispatchDetail(message: AgentMessage): string {
  return getSubagentTargetLabel(message);
}
