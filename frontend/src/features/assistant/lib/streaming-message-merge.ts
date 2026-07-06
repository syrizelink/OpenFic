import type { AgentMessage } from "@/lib/agent.types";

function isStreamingDeltaMessage(message: AgentMessage): boolean {
  return Boolean(message.payload?.is_delta && ["text", "reasoning", "tool"].includes(message.type));
}

export function getPersistedReasoningDurationMs(
  message: Pick<AgentMessage, "thinkingDurationMs" | "payload">,
): number {
  if (typeof message.thinkingDurationMs === "number") return message.thinkingDurationMs;
  const payloadDuration = message.payload?.duration_ms;
  return typeof payloadDuration === "number" ? payloadDuration : 0;
}

export function getReasoningDurationMs(
  message: Pick<
    AgentMessage,
    "timestamp" | "thinkingDurationMs" | "payload" | "isStreaming" | "status"
  >,
  now = Date.now(),
): number {
  const persistedDurationMs = getPersistedReasoningDurationMs(message);
  const isRunning = Boolean(message.isStreaming || message.status === "running");
  if (!isRunning) return persistedDurationMs;
  return Math.max(persistedDurationMs, Math.max(0, now - message.timestamp));
}

export function mergeStreamingMessage(previous: AgentMessage, message: AgentMessage): AgentMessage {
  const isDelta = Boolean(message.payload?.is_delta);
  const shouldPreservePreviousContent =
    !isDelta &&
    ["text", "reasoning"].includes(message.type) &&
    message.content === "" &&
    typeof previous.content === "string" &&
    previous.content.length > 0;
  const nextContent =
    isDelta && ["text", "reasoning"].includes(message.type)
      ? `${previous.content ?? ""}${message.content ?? ""}`
      : shouldPreservePreviousContent
        ? previous.content
        : (message.content ?? previous.content);

  return {
    ...previous,
    ...message,
    id: previous.id,
    payload: isDelta
      ? { ...(previous.payload ?? {}), ...(message.payload ?? {}) }
      : message.payload,
    content: nextContent,
    timestamp: isStreamingDeltaMessage(message) ? previous.timestamp : message.timestamp,
    toolArgs: message.toolArgs ?? previous.toolArgs,
    toolArgsText:
      message.status === "running" ? (message.toolArgsText ?? previous.toolArgsText) : undefined,
    partialToolArgs:
      message.status === "running"
        ? (message.partialToolArgs ?? previous.partialToolArgs)
        : undefined,
    toolResult: message.toolResult ?? previous.toolResult,
    toolSuccess: message.toolSuccess ?? previous.toolSuccess,
    isStreaming: message.status === "running" ? true : false,
    thinkingDurationMs: message.thinkingDurationMs ?? previous.thinkingDurationMs,
  };
}
