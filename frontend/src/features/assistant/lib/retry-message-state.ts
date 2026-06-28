import type { AgentMessage } from "@/lib/agent.types";

export function isRetryMessage(message: AgentMessage): boolean {
  return message.type === "retry";
}

export function clearRetryMessages(messages: AgentMessage[]): AgentMessage[] {
  return messages.filter((message) => !isRetryMessage(message));
}

export function upsertRetryMessage(
  messages: AgentMessage[],
  retryMessage: AgentMessage
): AgentMessage[] {
  return [...clearRetryMessages(messages), retryMessage];
}
