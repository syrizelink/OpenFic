import type { AgentMessage } from "@/lib/agent.types";

import type {
  AgentBlockDisplayMessage,
  ApprovalPanelItem,
  BlockDisplayMessage,
  QuestionPanelItem,
  SpecialPanelItem,
} from "./display-message-types";

const normalizedBlockMessageCache = new WeakMap<AgentMessage, BlockDisplayMessage | null>();
const normalizedApprovalItemCache = new WeakMap<AgentMessage, ApprovalPanelItem | null>();
const normalizedQuestionItemCache = new WeakMap<AgentMessage, QuestionPanelItem | null>();

function normalizeBlockMessage(message: AgentMessage): BlockDisplayMessage | null {
  if (message.display === "hidden") return null;

  switch (message.type) {
    case "user_request":
      return { ...message, type: "user_request", role: "user" };
    case "text":
      if (message.role === "user") {
        return { ...message, type: "user_request", role: "user" };
      }
      if (message.role === "assistant") {
        return { ...message, type: "agent_output", role: "assistant" };
      }
      return null;
    case "agent_output":
      return { ...message, type: "agent_output", role: "assistant" };
    case "reasoning":
    case "agent_thinking":
      return { ...message, type: "reasoning" };
    case "tool":
      if (!message.toolName) return null;
      return { ...message, type: "tool", toolName: message.toolName };
    case "retry":
      return { ...message, type: "retry" };
    case "compaction":
      return { ...message, type: "compaction" };
    case "completed":
      return { ...message, type: "completed" };
    case "error":
      return { ...message, type: "error" };
    case "node_start":
      return { ...message, type: "node_start" };
    case "node_end":
      return { ...message, type: "node_end" };
    default:
      return null;
  }
}

function isOpenSpecialPanelMessage(message: AgentMessage): boolean {
  return (
    message.display !== "hidden" &&
    (message.status === "pending" || message.status === "running" || !message.status)
  );
}

function getNormalizedBlockMessage(message: AgentMessage): BlockDisplayMessage | null {
  if (normalizedBlockMessageCache.has(message)) {
    return normalizedBlockMessageCache.get(message) ?? null;
  }

  const normalized = normalizeBlockMessage(message);
  normalizedBlockMessageCache.set(message, normalized);
  return normalized;
}

function normalizeApprovalItem(message: AgentMessage): ApprovalPanelItem | null {
  if (normalizedApprovalItemCache.has(message)) {
    return normalizedApprovalItemCache.get(message) ?? null;
  }

  if (message.type !== "approval" || !message.toolApproval || !isOpenSpecialPanelMessage(message)) {
    normalizedApprovalItemCache.set(message, null);
    return null;
  }
  const normalized: ApprovalPanelItem = {
    ...message,
    type: "approval",
    toolApproval: message.toolApproval,
  };
  normalizedApprovalItemCache.set(message, normalized);
  return normalized;
}

function normalizeQuestionItem(message: AgentMessage): QuestionPanelItem | null {
  if (normalizedQuestionItemCache.has(message)) {
    return normalizedQuestionItemCache.get(message) ?? null;
  }

  if (message.type !== "question" || !isOpenSpecialPanelMessage(message)) {
    normalizedQuestionItemCache.set(message, null);
    return null;
  }
  const normalized: QuestionPanelItem = {
    ...message,
    type: "question",
    questions: message.questions ?? [],
  };
  normalizedQuestionItemCache.set(message, normalized);
  return normalized;
}

export function normalizeDisplayMessages(messages: AgentMessage[]): BlockDisplayMessage[] {
  const normalizedMessages: BlockDisplayMessage[] = [];
  for (const message of messages) {
    const normalized = getNormalizedBlockMessage(message);
    if (normalized) normalizedMessages.push(normalized);
  }
  return normalizedMessages;
}

export function normalizeAgentBlockMessages(messages: AgentMessage[]): AgentBlockDisplayMessage[] {
  return normalizeDisplayMessages(messages).filter(
    (message): message is AgentBlockDisplayMessage =>
      message.type !== "user_request" &&
      message.type !== "node_start" &&
      message.type !== "node_end",
  );
}

export function normalizeSpecialPanelItems(messages: AgentMessage[]): SpecialPanelItem[] {
  return messages.reduce<SpecialPanelItem[]>((items, message) => {
    const approval = normalizeApprovalItem(message);
    if (approval) {
      items.push(approval);
      return items;
    }

    const question = normalizeQuestionItem(message);
    if (question) items.push(question);
    return items;
  }, []);
}
