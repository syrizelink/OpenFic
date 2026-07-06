import i18n from "@/i18n";
import type { AgentType } from "@/lib/agent.types";

export interface AgentMessageBlockProps {
  onApplyContent?: (content: string) => void;
}

export function getAgentName(agent: AgentType): string {
  return i18n.t(`assistant.agentNames.${agent}`);
}

export const AGENT_NAMES: Record<AgentType, string> = {
  primary: getAgentName("primary"),
  explorer: getAgentName("explorer"),
  composer: getAgentName("composer"),
  auditor: getAgentName("auditor"),
  writer: getAgentName("writer"),
  actor: getAgentName("actor"),
  reviewer: getAgentName("reviewer"),
};
