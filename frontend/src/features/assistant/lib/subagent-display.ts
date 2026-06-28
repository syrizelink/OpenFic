import type { AgentType } from "@/lib/agent.types";

const SUBAGENT_AGENT_LABELS: Record<AgentType, string> = {
  primary: "Primary",
  explorer: "Explorer",
  composer: "Composer",
  auditor: "Auditor",
  writer: "Writer",
  actor: "Actor",
  reviewer: "Reviewer",
};

function isAgentType(value: unknown): value is AgentType {
  return typeof value === "string" && value in SUBAGENT_AGENT_LABELS;
}

export function getSubagentAgentLabel(agentKey?: string | null): string {
  if (!agentKey) return "Unknown";
  return isAgentType(agentKey) ? SUBAGENT_AGENT_LABELS[agentKey] : agentKey;
}

export function formatSubagentDisplayLabel(
  agentKey?: string | null,
  agentNumber?: string | null
): string {
  const label = getSubagentAgentLabel(agentKey);
  if (!agentNumber) return label;
  return `${label} ( ${agentNumber} )`;
}
