import i18n from "@/i18n";
import type { AgentEvent, AgentMessage } from "@/lib/agent.types";

import { getReasoningDurationMs } from "../lib/streaming-message-merge";

const MESSAGE_TYPES_THAT_STOP_REASONING = new Set<AgentMessage["type"]>([
  "tool",
  "approval",
  "question",
  "compaction",
  "completed",
  "error",
]);

const HIDDEN_EVENT_TYPES_THAT_STOP_REASONING = new Set<string>([
  "token_usage",
  "node_start",
  "node_end",
  "stage_start",
  "stage_transfer",
  "iteration_start",
  "task_completed",
  "compaction_error",
]);

const EVENT_TYPES_SUPPRESSED_AFTER_ABORT = new Set<string>([
  "text",
  "reasoning",
  "tool",
  "approval",
  "question",
  "task_completed",
  "compaction",
  "compaction_error",
  "error",
  ...HIDDEN_EVENT_TYPES_THAT_STOP_REASONING,
]);

const CANCELLED_TOOL_RESULT: Record<string, unknown> = {
  type: "fail",
  success: false,
  recoverable: true,
  reason: "cancelled",
  message: i18n.t("assistant.userAbortedToolCall"),
  data: null,
  metadata: { interrupted: true },
};

function getActiveNodeStart(messages: AgentMessage[]): AgentMessage | null {
  let activeNode: AgentMessage | null = null;
  for (const message of messages) {
    if (message.type === "node_start") {
      activeNode = message;
      continue;
    }
    if (message.type === "node_end") {
      activeNode = null;
    }
  }
  return activeNode;
}

function createCancelledNodeEndMessage(nodeStart: AgentMessage): AgentMessage {
  const payload = nodeStart.payload ?? {};
  const node = typeof payload.node === "string" && payload.node ? payload.node : nodeStart.agent;
  const previousNode = payload.previous_node;
  const timestamp = Date.now();
  return {
    id: `${nodeStart.id}:cancelled-node-end:${timestamp}`,
    type: "node_end",
    role: "system",
    status: "error",
    display: "hidden",
    agent: nodeStart.agent,
    timestamp,
    payload: {
      node,
      phase: "end",
      status: "error",
      current_node: undefined,
      previous_node: typeof previousNode === "string" ? previousNode : undefined,
    },
  };
}

export function stopStreamingReasoning(messages: AgentMessage[]): AgentMessage[] {
  let hasRunningReasoning = false;
  const next = messages.map((message) => {
    if (message.type !== "reasoning" || !(message.isStreaming || message.status === "running"))
      return message;
    hasRunningReasoning = true;
    return {
      ...message,
      status: "completed" as const,
      isStreaming: false,
      thinkingDurationMs: getReasoningDurationMs(message),
    };
  });
  return hasRunningReasoning ? next : messages;
}

export function stopStreamingToolMessages(
  messages: AgentMessage[],
  status: "completed" | "error" = "completed",
): AgentMessage[] {
  let hasRunningTool = false;
  const next = messages.map((message) => {
    if (message.type !== "tool" || !(message.isStreaming || message.status === "running"))
      return message;
    hasRunningTool = true;
    const isError = status === "error";
    return {
      ...message,
      status,
      isStreaming: false,
      toolSuccess: isError ? false : message.toolSuccess,
      payload: isError
        ? {
            ...(message.payload ?? {}),
            success: false,
            tool_result: CANCELLED_TOOL_RESULT,
          }
        : message.payload,
      toolResult: isError ? CANCELLED_TOOL_RESULT : message.toolResult,
      content: isError ? i18n.t("assistant.userAbortedToolCall") : message.content,
    };
  });
  return hasRunningTool ? next : messages;
}

function markLastUnresolvedToolCancelled(messages: AgentMessage[]): AgentMessage[] {
  const lastToolIndex = messages.findLastIndex((message) => message.type === "tool");
  if (lastToolIndex < 0) return messages;
  const lastTool = messages[lastToolIndex];
  if (lastTool.status === "error" || lastTool.toolResult) return messages;

  const next = [...messages];
  next[lastToolIndex] = {
    ...lastTool,
    status: "error",
    isStreaming: false,
    toolSuccess: false,
    payload: {
      ...(lastTool.payload ?? {}),
      success: false,
      tool_result: CANCELLED_TOOL_RESULT,
    },
    toolResult: CANCELLED_TOOL_RESULT,
    content: i18n.t("assistant.userAbortedToolCall"),
  };
  return next;
}

export function cancelStreamingAgentMessages(messages: AgentMessage[]): AgentMessage[] {
  let changed = false;
  const activeNode = getActiveNodeStart(messages);
  const next = markLastUnresolvedToolCancelled(
    stopStreamingToolMessages(stopStreamingReasoning(messages), "error"),
  ).map((message) => {
    if (
      message.type !== "text" ||
      message.role !== "assistant" ||
      !(message.isStreaming || message.status === "running")
    )
      return message;
    changed = true;
    return {
      ...message,
      status: "completed" as const,
      isStreaming: false,
    };
  });
  if (activeNode) {
    return [...next, createCancelledNodeEndMessage(activeNode)];
  }
  return changed || next !== messages ? next : messages;
}

export function shouldSuppressAgentEventAfterAbort(event: Pick<AgentEvent, "type">): boolean {
  return EVENT_TYPES_SUPPRESSED_AFTER_ABORT.has(event.type);
}

export function shouldSuppressAgentErrorAfterCompactionError(
  event: Pick<AgentEvent, "type">,
  suppressNextError: boolean,
): boolean {
  return suppressNextError && event.type === "error";
}

export function shouldStopStreamingReasoningForAgentEvent(
  event: Pick<AgentEvent, "type" | "display">,
  message?: Pick<AgentMessage, "type" | "role">,
): boolean {
  if (message?.type === "reasoning") return false;
  if (message?.type === "text") return message.role === "assistant";
  if (message && MESSAGE_TYPES_THAT_STOP_REASONING.has(message.type)) return true;
  return event.display === "hidden" && HIDDEN_EVENT_TYPES_THAT_STOP_REASONING.has(event.type);
}

export function stopStreamingReasoningForAgentEvent(
  messages: AgentMessage[],
  event: Pick<AgentEvent, "type" | "display">,
  message?: Pick<AgentMessage, "type" | "role">,
): AgentMessage[] {
  if (!shouldStopStreamingReasoningForAgentEvent(event, message)) return messages;
  return stopStreamingReasoning(messages);
}
