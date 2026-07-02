import type { AgentMessage, AgentSessionStatus } from "../../../lib/agent.types";
import i18n from "@/i18n";

export const AGENT_STAGE_TEXT = {
  primary: i18n.t("assistant.agentStatus.primary"),
  explorer: i18n.t("assistant.agentStatus.explorer"),
  composer: i18n.t("assistant.agentStatus.composer"),
  writer: i18n.t("assistant.agentStatus.writer"),
  reviewer: i18n.t("assistant.agentStatus.reviewer"),
} as const;

export interface LoadedAgentSessionState {
  status: AgentSessionStatus;
  isRunning: boolean;
  currentStage: string;
}

function isActiveRunningMessage(message: AgentMessage | undefined): boolean {
  if (!message) return false;
  if (message.type === "tool" && message.toolName === "dispatch_subagent") return false;
  return message.status === "running" || message.isStreaming === true;
}

export function hasRunningAsyncSubagent(messages: AgentMessage[]): boolean {
  void messages;
  return false;
}

export function getBestEffortContinueStage(messages: AgentMessage[]): string {
  const lastMessage = messages[messages.length - 1];
  if (!lastMessage) return AGENT_STAGE_TEXT.primary;
  if (lastMessage.type === "tool_approval" || lastMessage.type === "approval") return i18n.t("assistant.applyingChanges");
  if (lastMessage.type === "tool") {
    return AGENT_STAGE_TEXT.writer;
  }
  return AGENT_STAGE_TEXT.primary;
}

export function getLoadedAgentSessionState({
  messages,
  isRemoteRunning,
}: {
  messages: AgentMessage[];
  isRemoteRunning?: boolean;
}): LoadedAgentSessionState {
  if (isRemoteRunning) {
    return {
      status: "running",
      isRunning: true,
      currentStage: getBestEffortContinueStage(messages),
    };
  }

  const lastMessage = messages[messages.length - 1];
  if (!lastMessage) return { status: "idle", isRunning: false, currentStage: "" };

  if (isRemoteRunning !== false && isActiveRunningMessage(lastMessage)) {
    return {
      status: "running",
      isRunning: true,
      currentStage: getBestEffortContinueStage(messages),
    };
  }

  if (lastMessage.type === "completed") return { status: "completed", isRunning: false, currentStage: "" };
  if (lastMessage.type === "error" || (lastMessage.type as string) === "cancelled") {
    return { status: "error", isRunning: false, currentStage: "" };
  }
  if (lastMessage.type === "clarification" || lastMessage.type === "question") {
    return { status: "waiting_answer", isRunning: false, currentStage: "" };
  }
  if (lastMessage.type === "tool_approval" || lastMessage.type === "approval") {
    return { status: "waiting_approval", isRunning: false, currentStage: "" };
  }
  return { status: "idle", isRunning: false, currentStage: "" };
}

export function shouldJoinLoadedAgentSession(state: LoadedAgentSessionState): boolean {
  return state.isRunning || state.status === "waiting_answer" || state.status === "waiting_approval";
}
