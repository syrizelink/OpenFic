const SUBAGENT_AGENT_LABELS: Record<string, string> = {
  build: "Build",
  plan: "Plan",
  explore: "Explore",
  composer: "Composer",
  auditor: "Auditor",
  writer: "Writer",
  actor: "Actor",
  reviewer: "Reviewer",
};

export function getSubagentAgentLabel(agentKey?: string | null): string {
  if (!agentKey) return "Unknown";
  return SUBAGENT_AGENT_LABELS[agentKey] ?? agentKey;
}

export function formatSubagentDisplayLabel(
  agentKey?: string | null,
  agentNumber?: string | null,
): string {
  const label = getSubagentAgentLabel(agentKey);
  if (!agentNumber) return label;
  return `${label} ( ${agentNumber} )`;
}
