import type { AgentMessage } from "@/lib/agent.types";

export const AGENT_RUNNING_STATUS = {
  considering: "considering",
  thinking: "thinking",
  writingReply: "writingReply",
  processingTask: "processingTask",
} as const;

export type AgentRunningStatus = (typeof AGENT_RUNNING_STATUS)[keyof typeof AGENT_RUNNING_STATUS];

export function getAgentRunningStatus(messages: AgentMessage[]): AgentRunningStatus {
  const activeMessage = messages.findLast(
    (message) =>
      message.status === "running" || message.status === "pending" || message.isStreaming === true,
  );
  if (!activeMessage) return AGENT_RUNNING_STATUS.considering;
  if (activeMessage.type === "reasoning") return AGENT_RUNNING_STATUS.thinking;
  if (
    activeMessage.type === "agent_output" ||
    (activeMessage.type === "text" && activeMessage.role === "assistant")
  )
    return AGENT_RUNNING_STATUS.writingReply;
  if (activeMessage.type === "tool") return AGENT_RUNNING_STATUS.processingTask;
  return AGENT_RUNNING_STATUS.considering;
}
