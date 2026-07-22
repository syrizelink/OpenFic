import { useCallback, useEffect, useRef, useState } from "react";

import { toast } from "@/components";
import i18n from "@/i18n";
import type {
  AgentMessage,
  AgentSessionStatus,
  SubagentSessionPayload,
  TokenUsageState,
} from "@/lib/agent.types";
import { fetchSubagentSession, submitAgentToolApproval } from "@/lib/api-client";
import type { TaskListItem } from "@/lib/task.types";

import {
  applyAgentTranscriptEventToLiveState,
  createAgentTranscriptLiveState,
  syncAgentTranscriptLiveState,
} from "../lib/agent-transcript-live-state";
import {
  failCompactionTranscriptState,
  getStageTextForAgentKey,
  getStageTextForStageKey,
  type AgentTranscriptState,
} from "../lib/agent-transcript-state";
import { createApprovalPreviewToolMessage } from "../lib/chapter-tool-preview";
import { createPendingApprovalEvent } from "../lib/subagent-session-approval";
import { joinSubagentSession, subscribeSubagentSessionEvents } from "../lib/subagent-socket";
import { buildAgentMessagesFromTaskMessages } from "../lib/task-message-agent-mapping";
import { shouldSuppressAgentErrorAfterCompactionError } from "./use-agent-session-message-state";

function resolveStageText(stage?: string): string {
  return getStageTextForAgentKey(stage) || stage || "";
}

function toSessionStatus(payload: SubagentSessionPayload | null): AgentSessionStatus {
  if (!payload) return "idle";
  if (payload.status === "error" || payload.status === "cancelled") return "error";
  if (payload.status === "waiting_user") return "waiting_approval";
  if (payload.status === "completed") return "completed";
  return payload.isRunning ? "running" : "idle";
}

function toPayloadStatus(
  status: AgentSessionStatus,
  current: SubagentSessionPayload["status"],
): SubagentSessionPayload["status"] {
  if (status === "error") return "error";
  if (status === "completed") return "completed";
  if (status === "waiting_answer" || status === "waiting_approval") return "waiting_user";
  if (status === "running") return "running";
  return current;
}

function buildTaskSnapshot(payload: SubagentSessionPayload): TaskListItem {
  const timestamp = payload.messages[0]?.createdAt ?? new Date().toISOString();
  return {
    id: payload.childRunId,
    projectId: "",
    title: payload.agentKey,
    tokenInput: payload.tokenInput,
    tokenOutput: payload.tokenOutput,
    tokenCache: payload.tokenCache,
    contextInputTokens: payload.contextInputTokens,
    isRunning: payload.isRunning,
    isFavorited: false,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
}

function toTokenUsage(payload: {
  tokenInput: number;
  tokenOutput: number;
  tokenCache: number;
  contextInputTokens: number;
  contextLength: number;
}): TokenUsageState {
  return {
    tokenInput: payload.tokenInput,
    tokenOutput: payload.tokenOutput,
    tokenCache: payload.tokenCache,
    contextInputTokens: payload.contextInputTokens,
    contextLength: payload.contextLength,
  };
}

function hasApprovalMessage(messages: AgentMessage[]): boolean {
  return messages.some(
    (message) =>
      (message.type === "approval" || message.type === "tool_approval") &&
      Boolean(message.toolApproval?.approval_id),
  );
}

function removeApprovalMessageById(messages: AgentMessage[], approvalId: string): AgentMessage[] {
  return messages.filter((message) => {
    if (message.type !== "approval" && message.type !== "tool_approval") return true;
    return message.toolApproval?.approval_id !== approvalId;
  });
}

export function useSubagentSession(
  childRunId: string | null,
  childThreadId: string | null = null,
  onTokenUsage?: (sessionId: string, usage: TokenUsageState) => void,
) {
  const [session, setSession] = useState<SubagentSessionPayload | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [status, setStatus] = useState<AgentSessionStatus>("idle");
  const [isRunning, setIsRunning] = useState(false);
  const [currentStage, setCurrentStage] = useState("");
  const [tokenUsage, setTokenUsage] = useState<TokenUsageState>({
    tokenInput: 0,
    tokenOutput: 0,
    tokenCache: 0,
    contextInputTokens: 0,
    contextLength: 0,
  });
  const transcriptStateRef = useRef(createAgentTranscriptLiveState());
  const suppressNextErrorAfterCompactionErrorRef = useRef(false);

  const commitTranscriptState = useCallback((nextState: AgentTranscriptState) => {
    syncAgentTranscriptLiveState(transcriptStateRef.current, nextState);
    setMessages(nextState.messages);
    setStatus(nextState.status);
    setIsRunning(nextState.isRunning);
    setCurrentStage(nextState.currentStage);
  }, []);

  const handleToolApproval = useCallback(
    async (approvalId: string, approved: boolean) => {
      const parentSessionId = session?.parentSessionId;
      if (!parentSessionId) return;

      try {
        const nextMessages = removeApprovalMessageById(
          transcriptStateRef.current.messages,
          approvalId,
        );
        const hasPendingApproval = hasApprovalMessage(nextMessages);
        commitTranscriptState({
          ...transcriptStateRef.current,
          messages: nextMessages,
          status: hasPendingApproval ? "waiting_approval" : "running",
          isRunning: !hasPendingApproval,
          currentStage: hasPendingApproval ? "" : i18n.t("assistant.applyingChanges"),
        });
        setSession((current) =>
          current
            ? {
                ...current,
                pendingApproval: null,
                status: hasPendingApproval ? "waiting_user" : "running",
                isRunning: !hasPendingApproval,
              }
            : current,
        );
        await submitAgentToolApproval(parentSessionId, approvalId, approved);
      } catch (error) {
        console.error("Subagent tool approval failed:", error);
        commitTranscriptState({
          ...transcriptStateRef.current,
          status: "error",
          isRunning: false,
          currentStage: "",
        });
        setSession((current) =>
          current
            ? {
                ...current,
                status: "error",
                isRunning: false,
              }
            : current,
        );
      }
    },
    [commitTranscriptState, session?.parentSessionId],
  );

  const load = useCallback(async () => {
    if (!childRunId) {
      setSession(null);
      setMessages([]);
      setStatus("idle");
      setIsRunning(false);
      setCurrentStage("");
      setTokenUsage({
        tokenInput: 0,
        tokenOutput: 0,
        tokenCache: 0,
        contextInputTokens: 0,
        contextLength: 0,
      });
      commitTranscriptState(createAgentTranscriptLiveState());
      return;
    }

    const payload = await fetchSubagentSession(childRunId);
    const nextTokenUsage = toTokenUsage(payload);
    const nextMessages = buildAgentMessagesFromTaskMessages(
      payload.messages,
      buildTaskSnapshot(payload),
      payload.messages[0]?.createdAt ?? new Date().toISOString(),
    );
    const nextState = createAgentTranscriptLiveState({
      messages: nextMessages,
      status: toSessionStatus(payload),
      isRunning: payload.isRunning,
      currentStage: payload.isRunning ? resolveStageText(payload.agentKey) : "",
    });
    const pendingApprovalEvent = createPendingApprovalEvent(
      payload.pendingApproval,
      payload.messages[payload.messages.length - 1]?.createdAt,
    );
    setSession(payload);
    commitTranscriptState(
      pendingApprovalEvent
        ? applyAgentTranscriptEventToLiveState(nextState, pendingApprovalEvent, {
            approvalPreviewFactory: createApprovalPreviewToolMessage,
            defaultRunningStage: getStageTextForAgentKey(payload.agentKey) || payload.agentKey,
            fallbackAgent: payload.agentKey,
            getStageTextForAgent: getStageTextForAgentKey,
            getStageTextForStage: getStageTextForStageKey,
          }).state
        : nextState,
    );
    setTokenUsage(nextTokenUsage);
    onTokenUsage?.(payload.childThreadId, nextTokenUsage);
  }, [childRunId, commitTranscriptState, onTokenUsage]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      void load();
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  useEffect(() => {
    if (!childRunId) return undefined;

    const targetThreadId = childThreadId || session?.childThreadId;
    if (!targetThreadId) return undefined;

    const cleanup = subscribeSubagentSessionEvents(
      targetThreadId,
      (event) => {
        if (event.type === "compaction_error") {
          suppressNextErrorAfterCompactionErrorRef.current = true;
          const payload = event.payload ?? {};
          const message =
            event.content ||
            (typeof payload.message === "string" ? payload.message : "") ||
            i18n.t("assistant.compactionFailed");
          toast.error(`${i18n.t("assistant.compactionFailed")}：${message}`);
          commitTranscriptState(
            failCompactionTranscriptState(
              transcriptStateRef.current,
              typeof payload.session_id === "string" ? payload.session_id : targetThreadId,
            ),
          );
          setSession((current) =>
            current ? { ...current, status: "error", isRunning: false, isActive: false } : current,
          );
          return;
        }

        if (
          shouldSuppressAgentErrorAfterCompactionError(
            event,
            suppressNextErrorAfterCompactionErrorRef.current,
          )
        ) {
          suppressNextErrorAfterCompactionErrorRef.current = false;
          commitTranscriptState(
            failCompactionTranscriptState(transcriptStateRef.current, targetThreadId),
          );
          setSession((current) =>
            current ? { ...current, status: "error", isRunning: false, isActive: false } : current,
          );
          return;
        }

        if (event.type === "token_usage") {
          const payload = event.payload ?? {};
          const nextTokenUsage = {
            tokenInput: Number(payload.token_input ?? 0),
            tokenOutput: Number(payload.token_output ?? 0),
            tokenCache: Number(payload.token_cache ?? 0),
            contextInputTokens: Number(payload.context_input_tokens ?? 0),
            contextLength: Number(payload.context_length ?? 0),
          };
          setTokenUsage(nextTokenUsage);
          onTokenUsage?.(targetThreadId, nextTokenUsage);
          setSession((current) =>
            current
              ? {
                  ...current,
                  tokenInput: nextTokenUsage.tokenInput,
                  tokenOutput: nextTokenUsage.tokenOutput,
                  tokenCache: nextTokenUsage.tokenCache,
                  contextInputTokens: nextTokenUsage.contextInputTokens,
                  contextLength: nextTokenUsage.contextLength,
                }
              : current,
          );
        }

        const result = applyAgentTranscriptEventToLiveState(transcriptStateRef.current, event, {
          approvalPreviewFactory: createApprovalPreviewToolMessage,
          defaultRunningStage:
            getStageTextForAgentKey(session?.agentKey) || session?.agentKey || "",
          fallbackAgent: session?.agentKey,
          getStageTextForAgent: getStageTextForAgentKey,
          getStageTextForStage: getStageTextForStageKey,
        });

        commitTranscriptState(result.state);
        setSession((current) => {
          if (!current) return current;
          const nextStatus = toPayloadStatus(result.state.status, current.status);
          const isTerminal = result.state.status === "completed" || result.state.status === "error";
          const nextPendingApproval =
            result.message?.type === "approval"
              ? (result.message.payload ?? current.pendingApproval)
              : nextStatus === "waiting_user"
                ? current.pendingApproval
                : null;
          return {
            ...current,
            status: nextStatus,
            isRunning: result.state.isRunning,
            isActive: isTerminal ? false : current.isActive || result.state.isRunning,
            pendingApproval: nextPendingApproval,
          };
        });
      },
      (error) => {
        setSession((current) =>
          current ? { ...current, status: "error", isRunning: false, isActive: false } : current,
        );
        commitTranscriptState({
          messages: transcriptStateRef.current.messages,
          status: "error",
          isRunning: false,
          currentStage: "",
        });
        console.warn("Subagent session stream disconnected", error);
      },
    );

    void joinSubagentSession(targetThreadId).catch((error) => {
      setSession((current) =>
        current ? { ...current, status: "error", isRunning: false, isActive: false } : current,
      );
      commitTranscriptState({
        messages: transcriptStateRef.current.messages,
        status: "error",
        isRunning: false,
        currentStage: "",
      });
      console.warn("Failed to join subagent session stream", error);
    });

    return () => {
      cleanup();
    };
  }, [
    childRunId,
    childThreadId,
    commitTranscriptState,
    onTokenUsage,
    session?.agentKey,
    session?.childThreadId,
  ]);

  return {
    session,
    messages,
    status,
    isRunning,
    currentStage,
    tokenUsage,
    load,
    handleToolApproval,
  };
}
