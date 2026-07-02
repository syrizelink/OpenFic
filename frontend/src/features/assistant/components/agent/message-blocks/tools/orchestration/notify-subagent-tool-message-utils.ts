import type { AgentMessage } from "@/lib/agent.types";
import i18n from "@/i18n";

import { getSubagentTargetLabel } from "./subagent-tool-message-utils";

export function getNotifySubagentTitle(): string {
  return i18n.t("assistant.subagentAction.notify");
}

export function getNotifySubagentDetail(message: AgentMessage): string {
  return getSubagentTargetLabel(message);
}
