import { useCallback, useEffect, useRef, useState } from "react";

import { toast } from "@/components";
import i18n from "@/i18n";
import type {
  ActiveSubagentState,
  AgentEvent,
  AgentMessage,
  AgentSessionStatus,
  SubagentSessionPayload,
  TokenUsageState,
} from "@/lib/agent.types";
import {
  fetchSubagentSession,
  submitAgentToolApproval,
  cancelSubagentSession,
} from "@/lib/api-client";
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
import { clearRetryMessages } from "../lib/retry-message-state";
import {
  createStreamingDeltaCoalescer,
  isStreamingDeltaEvent,
} from "../lib/streaming-delta-coalescer";
import { createPendingApprovalEvent } from "../lib/subagent-session-approval";
import { joinSubagentSession, subscribeSubagentSessionEvents } from "../lib/subagent-socket";
import { buildAgentMessagesFromTaskMessages } from "../lib/task-message-agent-mapping";
import { prependAgentMessages, useAgentMessagePagination } from "./use-agent-message-pagination";
import { shouldSuppressAgentErrorAfterCompactionError } from "./use-agent-session-message-state";

const DEFAULT_RUNNING_STAGE = i18n.t("assistant.runningStatus.considering");

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
    cost: payload.cost,
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
  const activeSession = session?.childRunId === childRunId ? session : null;
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [sessionLoadVersion, setSessionLoadVersion] = useState(0);
  const [loadState, setLoadState] = useState<{ childRunId: string | null; isLoading: boolean }>({
    childRunId: null,
    isLoading: false,
  });
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
  const currentRequestIdRef = useRef<string | null>(null);
  const retiredRequestIdsRef = useRef(new Set<string>());
  const eventVersionRef = useRef(0);
  const activeChildRunIdRef = useRef<string | null>(null);

  const commitTranscriptState = useCallback((nextState: AgentTranscriptState) => {
    syncAgentTranscriptLiveState(transcriptStateRef.current, nextState);
    setMessages(nextState.messages);
    setStatus(nextState.status);
    setIsRunning(nextState.isRunning);
    setCurrentStage(nextState.currentStage);
  }, []);

  const fetchEarlierPage = useCallback(async (runId: string, cursor: number) => {
    const payload = await fetchSubagentSession(runId, cursor);
    return {
      ...payload,
      messages: buildAgentMessagesFromTaskMessages(
        payload.messages,
        buildTaskSnapshot(payload),
        payload.messages[0]?.createdAt ?? new Date().toISOString(),
      ),
    };
  }, []);
  const prependEarlierPage = useCallback(
    (older: AgentMessage[]) => {
      const current = transcriptStateRef.current;
      commitTranscriptState({
        ...current,
        messages: prependAgentMessages(current.messages, older),
      });
    },
    [commitTranscriptState],
  );
  const { resetPagination, invalidatePagination, ...messagePagination } = useAgentMessagePagination(
    fetchEarlierPage,
    prependEarlierPage,
  );
  const loadGenerationRef = useRef(0);

  const applySubagentEvent = useCallback(
    (event: AgentEvent) => {
      const payload = event.payload ?? {};
      const requestId =
        typeof payload.requestId === "string"
          ? payload.requestId
          : typeof payload.request_id === "string"
            ? payload.request_id
            : undefined;
      if (
        requestId &&
        (requestId !== currentRequestIdRef.current ||
          (event.type === "node_start" && event.status === "running"))
      ) {
        if (retiredRequestIdsRef.current.has(requestId)) return;
        if (currentRequestIdRef.current && currentRequestIdRef.current !== requestId)
          retiredRequestIdsRef.current.add(currentRequestIdRef.current);
        currentRequestIdRef.current = requestId;
        suppressNextErrorAfterCompactionErrorRef.current = false;
        commitTranscriptState({
          ...transcriptStateRef.current,
          messages: transcriptStateRef.current.messages.filter(
            (item) => item.payload?.run_error !== true,
          ),
        });
        setSession((current) =>
          current ? { ...current, currentRequestId: requestId, currentError: null } : current,
        );
      }
      const errorRoundId = typeof payload.round_id === "string" ? payload.round_id : undefined;
      if (event.type === "error" && errorRoundId) {
        if (
          retiredRequestIdsRef.current.has(errorRoundId) ||
          (currentRequestIdRef.current && currentRequestIdRef.current !== errorRoundId)
        )
          return;
        currentRequestIdRef.current = errorRoundId;
      }
      eventVersionRef.current += 1;
      const result = applyAgentTranscriptEventToLiveState(transcriptStateRef.current, event, {
        approvalPreviewFactory: createApprovalPreviewToolMessage,
        defaultRunningStage: DEFAULT_RUNNING_STAGE,
        fallbackAgent: activeSession?.agentKey,
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
          currentRequestId: currentRequestIdRef.current,
          status: nextStatus,
          isRunning: result.state.isRunning,
          isActive: isTerminal ? false : current.isActive || result.state.isRunning,
          pendingApproval: nextPendingApproval,
          currentError:
            event.type === "error" && errorRoundId
              ? {
                  type: String(payload.type ?? "error"),
                  reason: event.content ?? "",
                  roundId: errorRoundId,
                }
              : result.state.isRunning || result.state.status === "completed"
                ? null
                : current.currentError,
        };
      });
      return result;
    },
    [activeSession?.agentKey, commitTranscriptState],
  );

  const applySubagentEventRef = useRef(applySubagentEvent);
  applySubagentEventRef.current = applySubagentEvent;

  const deltaCoalescerRef = useRef<ReturnType<typeof createStreamingDeltaCoalescer> | null>(null);
  if (deltaCoalescerRef.current === null) {
    deltaCoalescerRef.current = createStreamingDeltaCoalescer((events) => {
      for (const event of events) {
        applySubagentEventRef.current(event);
      }
    });
  }

  const handleToolApproval = useCallback(
    async (approvalId: string, approved: boolean) => {
      const parentSessionId = activeSession?.parentSessionId;
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
    [activeSession?.parentSessionId, commitTranscriptState],
  );

  const cancelSession = useCallback(async () => {
    const parentSessionId = activeSession?.parentSessionId;
    if (!parentSessionId || !childRunId) return;
    try {
      await cancelSubagentSession(parentSessionId, childRunId);
    } catch (error) {
      console.error("Failed to cancel subagent session:", error);
      toast.error(i18n.t("assistant.cancelSubagentFailed"));
      return;
    }
    commitTranscriptState({
      ...transcriptStateRef.current,
      messages: clearRetryMessages(transcriptStateRef.current.messages),
      status: "error",
      isRunning: false,
      currentStage: "",
    });
    setSession((current) =>
      current ? { ...current, status: "cancelled", isRunning: false, isActive: false } : current,
    );
  }, [activeSession?.parentSessionId, childRunId, commitTranscriptState]);

  const load = useCallback(async () => {
    const generation = ++loadGenerationRef.current;
    resetPagination(null);
    if (activeChildRunIdRef.current !== childRunId) {
      deltaCoalescerRef.current?.dispose();
      activeChildRunIdRef.current = childRunId;
      eventVersionRef.current = 0;
      currentRequestIdRef.current = null;
      retiredRequestIdsRef.current.clear();
      suppressNextErrorAfterCompactionErrorRef.current = false;
      setSession(null);
      setTokenUsage({
        tokenInput: 0,
        tokenOutput: 0,
        tokenCache: 0,
        contextInputTokens: 0,
        contextLength: 0,
      });
      commitTranscriptState(createAgentTranscriptLiveState());
    }
    if (!childRunId) return;
    const eventVersion = eventVersionRef.current;

    setLoadState({ childRunId, isLoading: true });
    let payload: SubagentSessionPayload;
    try {
      payload = await fetchSubagentSession(childRunId);
    } catch (error) {
      if (generation !== loadGenerationRef.current) return;
      setLoadState({ childRunId, isLoading: false });
      if (transcriptStateRef.current.messages.length === 0) {
        setSession(null);
        commitTranscriptState(createAgentTranscriptLiveState({ status: "error" }));
      }
      throw error;
    }
    if (generation !== loadGenerationRef.current) return;
    setLoadState({ childRunId, isLoading: false });
    if (eventVersion !== eventVersionRef.current) {
      const currentState = transcriptStateRef.current;
      const runError = currentState.messages.findLast(
        (message) => message.payload?.run_error === true,
      );
      const roundId = runError?.payload?.round_id;
      setSession(
        (current) =>
          current ?? {
            ...payload,
            currentRequestId: currentRequestIdRef.current,
            status: toPayloadStatus(currentState.status, payload.status),
            isRunning: currentState.isRunning,
            currentError:
              runError && typeof roundId === "string"
                ? {
                    type: String(runError.payload?.type ?? "error"),
                    reason: runError.content ?? "",
                    roundId,
                  }
                : null,
          },
      );
      resetPagination(childRunId, payload);
      commitTranscriptState({
        ...currentState,
        messages: prependAgentMessages(
          currentState.messages,
          buildAgentMessagesFromTaskMessages(
            payload.messages,
            buildTaskSnapshot(payload),
            payload.messages[0]?.createdAt ?? new Date().toISOString(),
          ),
        ),
      });
      return;
    }
    if (payload.currentRequestId && retiredRequestIdsRef.current.has(payload.currentRequestId))
      return;
    resetPagination(childRunId, payload);
    const nextTokenUsage = toTokenUsage(payload);
    const nextMessages = buildAgentMessagesFromTaskMessages(
      payload.messages,
      buildTaskSnapshot(payload),
      payload.messages[0]?.createdAt ?? new Date().toISOString(),
    );
    const requestId = payload.currentRequestId;
    const currentError = payload.currentError?.roundId === requestId ? payload.currentError : null;
    if (currentRequestIdRef.current && currentRequestIdRef.current !== requestId)
      retiredRequestIdsRef.current.add(currentRequestIdRef.current);
    currentRequestIdRef.current = requestId;
    if (currentError) {
      nextMessages.push({
        id: `run-error:${currentError.roundId}`,
        type: "error",
        role: "system",
        status: "error",
        display: "list",
        timestamp: Date.now(),
        content: currentError.reason,
        payload: { run_error: true, round_id: currentError.roundId, type: currentError.type },
      });
    }
    const nextState = createAgentTranscriptLiveState({
      messages: nextMessages,
      status: currentError ? "error" : toSessionStatus(payload),
      isRunning: !currentError && payload.isRunning,
      currentStage: !currentError && payload.isRunning ? DEFAULT_RUNNING_STAGE : "",
    });
    const pendingApprovalEvent = createPendingApprovalEvent(
      payload.pendingApproval,
      payload.messages[payload.messages.length - 1]?.createdAt,
    );
    setSession({ ...payload, currentError, isRunning: nextState.isRunning });
    setSessionLoadVersion((version) => version + 1);
    commitTranscriptState(
      pendingApprovalEvent
        ? applyAgentTranscriptEventToLiveState(nextState, pendingApprovalEvent, {
            approvalPreviewFactory: createApprovalPreviewToolMessage,
            defaultRunningStage: DEFAULT_RUNNING_STAGE,
            fallbackAgent: payload.agentKey,
            getStageTextForAgent: getStageTextForAgentKey,
            getStageTextForStage: getStageTextForStageKey,
          }).state
        : nextState,
    );
    setTokenUsage(nextTokenUsage);
    onTokenUsage?.(payload.childThreadId, nextTokenUsage);
  }, [childRunId, commitTranscriptState, onTokenUsage, resetPagination]);

  useEffect(() => {
    let cancelled = false;
    void load().catch(() => {
      if (!cancelled) toast.error(i18n.t("writing.aiSidebar.taskLoadFailed"));
    });
    return () => {
      cancelled = true;
      loadGenerationRef.current += 1;
      invalidatePagination();
    };
  }, [invalidatePagination, load]);

  const handleStatusEvent = useCallback(
    (event: ActiveSubagentState) => {
      if (event.childRunId !== childRunId) return;
      void load().catch((error) => console.warn("Failed to refresh subagent request", error));
    },
    [childRunId, load],
  );

  useEffect(() => {
    if (!childRunId) return undefined;

    const targetThreadId = childThreadId || activeSession?.childThreadId;
    if (!targetThreadId) return undefined;
    let cancelled = false;

    const cleanup = subscribeSubagentSessionEvents(
      targetThreadId,
      (event) => {
        if (cancelled) return;
        const roundId = event.payload?.round_id;
        if (
          event.type === "error" &&
          typeof roundId === "string" &&
          (retiredRequestIdsRef.current.has(roundId) ||
            (currentRequestIdRef.current && currentRequestIdRef.current !== roundId))
        )
          return;
        if (isStreamingDeltaEvent(event)) {
          deltaCoalescerRef.current?.push(event);
          return;
        }
        deltaCoalescerRef.current?.flush();

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

        applySubagentEvent(event);
      },
      (error) => {
        if (cancelled) return;
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
      if (cancelled) return;
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
      cancelled = true;
      cleanup();
      deltaCoalescerRef.current?.dispose();
    };
  }, [
    applySubagentEvent,
    childRunId,
    childThreadId,
    commitTranscriptState,
    onTokenUsage,
    activeSession?.agentKey,
    activeSession?.childThreadId,
  ]);

  return {
    session: activeSession,
    isLoading: Boolean(childRunId && (loadState.childRunId !== childRunId || loadState.isLoading)),
    ...messagePagination,
    sessionLoadVersion,
    messages,
    status,
    isRunning,
    currentStage,
    tokenUsage,
    load,
    handleToolApproval,
    cancelSession,
    handleStatusEvent,
  };
}
