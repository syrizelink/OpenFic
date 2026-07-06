import i18n from "@/i18n";
import type { AgentMessage, AgentSessionStatus } from "@/lib/agent.types";

import { upsertRetryMessage } from "../lib/retry-message-state";

const SOCKET_CONNECTION_ERROR_KIND = "socket_connection";

interface ApplyTransportReconnectStateInput {
  messages: AgentMessage[];
  error: Error;
  attempt: number;
  maxAttempts?: number;
  currentStage?: string;
  fallbackStage: string;
  preservedStatus?: AgentSessionStatus;
}

interface TransportReconnectState {
  messages: AgentMessage[];
  status: AgentSessionStatus;
  isRunning: boolean;
  currentStage: string;
}

function normalizeReconnectStatus(status: AgentSessionStatus | undefined): AgentSessionStatus {
  if (status === "waiting_answer" || status === "waiting_approval" || status === "running") {
    return status;
  }
  return "running";
}

export function isTransportConnectionErrorMessage(message: AgentMessage): boolean {
  if (message.type !== "error") return false;
  const errorKind = message.payload?.error_kind;
  if (errorKind === SOCKET_CONNECTION_ERROR_KIND) return true;
  return /^Agent 连接失败[:：]/.test(message.content?.trim() ?? "");
}

function clearTransportConnectionErrorMessages(messages: AgentMessage[]): AgentMessage[] {
  return messages.filter((message) => !isTransportConnectionErrorMessage(message));
}

function createTransportReconnectRetryMessage({
  error,
  attempt,
  maxAttempts,
}: {
  error: Error;
  attempt: number;
  maxAttempts?: number;
}): AgentMessage {
  return {
    id: "socket-transport-retry",
    type: "retry",
    role: "system",
    status: "running",
    display: "list",
    timestamp: Date.now(),
    content: error.message || i18n.t("assistant.connectionFailed"),
    payload: {
      attempt,
      max_attempts: maxAttempts ?? attempt,
      retry_kind: SOCKET_CONNECTION_ERROR_KIND,
    },
  };
}

export function applyTransportReconnectState({
  messages,
  error,
  attempt,
  maxAttempts,
  currentStage,
  fallbackStage,
  preservedStatus,
}: ApplyTransportReconnectStateInput): TransportReconnectState {
  const nextStatus = normalizeReconnectStatus(preservedStatus);
  const retryMessage = createTransportReconnectRetryMessage({
    error,
    attempt,
    maxAttempts,
  });

  return {
    messages: upsertRetryMessage(clearTransportConnectionErrorMessages(messages), retryMessage),
    status: nextStatus,
    isRunning: nextStatus === "running",
    currentStage: nextStatus === "running" ? currentStage || fallbackStage : currentStage || "",
  };
}
