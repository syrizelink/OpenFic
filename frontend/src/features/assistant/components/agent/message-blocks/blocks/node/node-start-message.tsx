import { Box } from "@radix-ui/themes";
import { useEffect, useState } from "react";

import i18n from "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import { getAgentName } from "../../../agent-message.types";
import { formatElapsedDuration } from "../../shared/message-duration";

interface NodeStartMessageProps {
  message: AgentMessage;
  startedAt?: number;
  endedAt?: number;
  elapsedBaseMs?: number;
  isCollapsed?: boolean;
  onToggle?: () => void;
}

function getAgentLabel(message: AgentMessage): string {
  if (message.agent) return getAgentName(message.agent);

  const payloadNode = message.payload?.node;
  if (typeof payloadNode === "string" && payloadNode.trim()) return getAgentName(payloadNode);

  return i18n.t("assistant.agentNames.unknown");
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
    <Box
      className="agent-node-divider"
      data-collapsed={isCollapsed ? "true" : "false"}
    >
      <Box
        className="agent-node-divider-line"
        aria-hidden="true"
      />
      <button
        type="button"
        className="agent-node-divider-toggle"
        aria-expanded={!isCollapsed}
        aria-label={i18n.t("assistant.node.toggleAriaLabel", {
          agent: agentLabel,
          state: isCollapsed
            ? i18n.t("assistant.node.collapsed")
            : i18n.t("assistant.node.expanded"),
        })}
        onClick={onToggle}
      >
        <span className="agent-node-divider-agent">{agentLabel}</span>
        <span className="agent-node-divider-status">{i18n.t("assistant.node.processed")}</span>
        <span className="agent-node-divider-timer">{formatElapsedDuration(elapsedMs)}</span>
      </button>
    </Box>
  );
}
