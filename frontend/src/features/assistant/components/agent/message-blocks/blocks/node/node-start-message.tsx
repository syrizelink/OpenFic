import { useEffect, useState } from "react";
import { Box } from "@radix-ui/themes";

import type { AgentMessage, AgentType } from "@/lib/agent.types";

import { AGENT_NAMES } from "../../../agent-message.types";
import { formatElapsedDuration } from "../../shared/message-duration";

interface NodeStartMessageProps {
  message: AgentMessage;
  startedAt?: number;
  endedAt?: number;
  elapsedBaseMs?: number;
  isCollapsed?: boolean;
  onToggle?: () => void;
}

function isAgentType(value: unknown): value is AgentType {
  return typeof value === "string" && value in AGENT_NAMES;
}

function getAgentLabel(message: AgentMessage): string {
  if (isAgentType(message.agent)) return AGENT_NAMES[message.agent];

  const payloadNode = message.payload?.node;
  if (isAgentType(payloadNode)) return AGENT_NAMES[payloadNode];
  if (typeof payloadNode === "string" && payloadNode.trim()) return payloadNode.trim();

  return "Agent";
}

export function NodeStartMessage({
  message,
  startedAt,
  endedAt,
  elapsedBaseMs = 0,
  isCollapsed = false,
  onToggle,
}: NodeStartMessageProps) {
  const startTime = startedAt ?? message.timestamp;
  const hasEnded = typeof endedAt === "number";
  const [now, setNow] = useState(() => Date.now());
  const agentLabel = getAgentLabel(message);
  const elapsedMs = Math.max(0, elapsedBaseMs + (hasEnded ? endedAt : now) - startTime);

  useEffect(() => {
    if (hasEnded) return;

    const intervalId = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(intervalId);
  }, [hasEnded]);

  return (
    <Box className="agent-node-divider" data-collapsed={isCollapsed ? "true" : "false"}>
      <Box className="agent-node-divider-line" aria-hidden="true" />
      <button
        type="button"
        className="agent-node-divider-toggle"
        aria-expanded={!isCollapsed}
        aria-label={`${agentLabel}节点${isCollapsed ? "已收起" : "已展开"}`}
        onClick={onToggle}
      >
        <span className="agent-node-divider-agent">{agentLabel}</span>
        <span className="agent-node-divider-status">已处理</span>
        <span className="agent-node-divider-timer">{formatElapsedDuration(elapsedMs)}</span>
      </button>
    </Box>
  );
}
