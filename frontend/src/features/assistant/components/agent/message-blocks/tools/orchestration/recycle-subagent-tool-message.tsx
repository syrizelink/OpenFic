import type { AgentMessage } from "@/lib/agent.types";
import i18n from "@/i18n";

import { getSubagentTargetLabel } from "./subagent-tool-message-utils";

export function getRecycleSubagentTitle(): string {
  return i18n.t("assistant.subagentAction.recycle");
}

export function getRecycleSubagentDetail(message: AgentMessage): string {
  return getSubagentTargetLabel(message);
}
