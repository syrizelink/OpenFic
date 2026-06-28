import type { AgentPendingMessage, AgentPendingMessageAction } from "@/lib/agent.types";

export interface PendingUserMessageEvent {
  action: AgentPendingMessageAction;
  messageId: string;
  content?: string;
  createdAt?: string;
}

export function createPendingUserMessage(message: AgentPendingMessage): AgentPendingMessage {
  return {
    messageId: message.messageId,
    content: message.content,
    createdAt: message.createdAt,
  };
}

export function applyPendingUserMessageEvent(
  current: AgentPendingMessage | null,
  event: PendingUserMessageEvent,
): AgentPendingMessage | null {
  if (!event.messageId) return current;

  if (event.action === "queued") {
    if (!event.content || !event.createdAt) return current;
    return createPendingUserMessage({
      messageId: event.messageId,
      content: event.content,
      createdAt: event.createdAt,
    });
  }

  if (current?.messageId !== event.messageId) return current;
  return null;
}
