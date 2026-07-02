import type { AgentMessage } from "@/lib/agent.types";
import i18n from "@/i18n";

import { getSubagentTargetLabel } from "./subagent-tool-message-utils";

export function getSubagentDispatchTitle(message: AgentMessage): string {
  void message;
  return i18n.t("assistant.subagentAction.dispatch");
}

export function getSubagentDispatchDetail(message: AgentMessage): string {
  return getSubagentTargetLabel(message);
}
