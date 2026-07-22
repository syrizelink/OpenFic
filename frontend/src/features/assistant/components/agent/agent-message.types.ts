import i18n from "@/i18n";
import type { AgentType } from "@/lib/agent.types";

export interface AgentMessageBlockProps {
  onApplyContent?: (content: string) => void;
}

export function getAgentName(agent: AgentType): string {
  const translated = i18n.t(`assistant.agentNames.${agent}`);
  return translated === `assistant.agentNames.${agent}` ? agent : translated;
}

export const AGENT_NAMES = {
  build: getAgentName("build"),
  plan: getAgentName("plan"),
  explore: getAgentName("explore"),
  composer: getAgentName("composer"),
  auditor: getAgentName("auditor"),
  writer: getAgentName("writer"),
  actor: getAgentName("actor"),
  reviewer: getAgentName("reviewer"),
} as const;
