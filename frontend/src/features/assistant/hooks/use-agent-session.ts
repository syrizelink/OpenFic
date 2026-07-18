/**
 * Agent Hook
 *
 * Agent 会话管理 Hook
 */

import { useQueryClient } from "@tanstack/react-query";
import { useState, useCallback, useEffect, useRef } from "react";

import { toast } from "@/components";
import i18n from "@/i18n";
import type {
  AgentMessage,
  AgentPendingMessage,
  AgentSessionCreateResponse,
  AgentSessionStatus,
  AgentEvent,
  ReasoningEffort,
} from "@/lib/agent.types";
import type { TokenUsageState } from "@/lib/agent.types";
import type { AgentForkResponse } from "@/lib/agent.types";
import {
  cancelPendingAgentMessage,
  compactAgentSession,
  createAgentSession,
  forkAgentSession,
  sendAgentMessage,
  submitAgentQuestionAnswer,
  rollbackAgentRevision,
  cancelAgentSession,
  submitAgentToolApproval,
} from "@/lib/api-client";

import { joinAgentSession, subscribeAgentSessionEvents } from "../lib/agent-socket";
import {
  applyAgentTranscriptEventToLiveState,
  createAgentTranscriptLiveState,
  syncAgentTranscriptLiveState,
} from "../lib/agent-transcript-live-state";
import {
  abortCompactionTranscriptState,
  failCompactionTranscriptState,
  getStageTextForAgentKey,
  getStageTextForStageKey,
  restoreManualCompactionTranscriptState,
  type AgentTranscriptState,
} from "../lib/agent-transcript-state";
import { createApprovalPreviewToolMessage } from "../lib/chapter-tool-preview";
import {
  applyPendingUserMessageEvent,
  createPendingUserMessage,
} from "../lib/pending-user-message-state";
import { clearRetryMessages } from "../lib/retry-message-state";
import { applyTransportReconnectState } from "./agent-session-transport-state";
import {
  cancelStreamingAgentMessages,
  shouldSuppressAgentErrorAfterCompactionError,
  shouldSuppressAgentEventAfterAbort,
} from "./use-agent-session-message-state";
import {
  AGENT_STAGE_TEXT,
  getBestEffortContinueStage,
  getLoadedAgentSessionState,
  hasRunningAsyncSubagent,
  shouldJoinLoadedAgentSession,
} from "./use-agent-session-reconnect";
import type { ClarificationAnswerItem } from "../components/agent/message-blocks/messages/special/clarification-flow-state";

function isUserTextMessage(message: AgentMessage | undefined): message is AgentMessage {
  return Boolean(
    message &&
    (message.type === "user_request" || (message.type === "text" && message.role === "user")),
  );
}

function createOptimisticUserMessage(content: string): AgentMessage {
  const timestamp = Date.now();
  return {
    id: `optimistic-user-${timestamp}`,
    type: "user_request",
    role: "user",
    timestamp,
    content,
    isDraft: true,
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function getString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function getAgentApiErrorMessage(error: unknown, fallback: string): string {
  const response = isRecord(error) ? error.response : undefined;
  const responseData = isRecord(response) ? response.data : undefined;
  if (isRecord(responseData)) {
    const detail = responseData.detail;
    const detailMessage = isRecord(detail)
      ? getString(detail.message) || getString(detail.reason) || getString(detail.error)
      : getString(detail);
    return (
      getString(responseData.message) ||
      detailMessage ||
      getString(responseData.detail) ||
      getString(responseData.reason) ||
      getString(responseData.error) ||
      fallback
    );
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

interface UseAgentSessionOptions {
  projectId: string;
  modelId: string;
  reasoningEffort?: ReasoningEffort;
  agentKey?: string;
  maxIterations?: number;
  onTokenUsage?: (sessionId: string, usage: TokenUsageState) => void;
  onTaskUsageSnapshot?: (payload: {
    sessionId: string;
    taskId: string;
    tokenInput: number;
    tokenOutput: number;
    tokenCache: number;
  }) => void;
  onTaskUsageDelta?: (payload: {
    sessionId: string;
    taskId: string;
    tokenInput: number;
    tokenOutput: number;
    tokenCache: number;
  }) => void;
  onTaskTitleUpdated?: (taskId: string, title: string, updatedAt?: string) => void;
  onSessionCreated?: (session: AgentSessionCreateResponse) => void;
}

export function useAgentSession({
  projectId,
  modelId,
  reasoningEffort,
  agentKey,
  maxIterations = 5,
  onTokenUsage,
  onTaskUsageSnapshot,
  onTaskUsageDelta,
  onTaskTitleUpdated,
  onSessionCreated,
}: UseAgentSessionOptions) {
  const queryClient = useQueryClient();
  const socketUnsubscribeRef = useRef<(() => void) | null>(null);
  const ignoredApprovalIdsRef = useRef<Set<string>>(new Set());
  const suppressSocketEventsAfterAbortRef = useRef(false);
  const sessionIdRef = useRef<string | null>(null);
  const activeModelIdRef = useRef<string | null>(null);
  const pendingMessageRef = useRef<AgentPendingMessage | null>(null);
  const isCompactingRef = useRef(false);
  const manualCompactionPreviousStateRef = useRef<Pick<
    AgentTranscriptState,
    "status" | "isRunning" | "currentStage"
  > | null>(null);
  const suppressNextErrorAfterCompactionErrorRef = useRef(false);
  const transcriptStateRef = useRef(createAgentTranscriptLiveState());
  const transportRetryAttemptRef = useRef(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [pendingMessage, setPendingMessage] = useState<AgentPendingMessage | null>(null);
  const [status, setStatus] = useState<AgentSessionStatus>("idle");
  const [isRunning, setIsRunning] = useState(false);
  const [isCompacting, setIsCompacting] = useState(false);
  const [isRollbacking, setIsRollbacking] = useState(false);
  const [currentStage, setCurrentStage] = useState<string>("");

  useEffect(() => {
    return () => {
      socketUnsubscribeRef.current?.();
      socketUnsubscribeRef.current = null;
    };
  }, []);

  const invalidateChapterQueries = useCallback(
    (targetChapterId?: string) => {
      queryClient.invalidateQueries({ queryKey: ["volume-tree", projectId] });
      if (targetChapterId) {
        queryClient.invalidateQueries({ queryKey: ["chapter", targetChapterId] });
      }
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    [projectId, queryClient],
  );

  const invalidateNoteQueries = useCallback(
    (targetNoteId?: string) => {
      queryClient.invalidateQueries({ queryKey: ["note-tree", projectId] });
      if (targetNoteId) {
        queryClient.invalidateQueries({ queryKey: ["note", targetNoteId] });
      }
    },
    [projectId, queryClient],
  );

  const invalidateWorldEntryQueries = useCallback(
    (targetWorldInfoId?: string, targetEntryId?: string, operation?: string) => {
      if (targetWorldInfoId) {
        queryClient.invalidateQueries({ queryKey: ["world-info-entries", targetWorldInfoId] });
      } else {
        queryClient.invalidateQueries({ queryKey: ["world-info-entries"] });
      }
      if (!targetEntryId) return;

      if (operation === "delete") {
        queryClient.removeQueries({
          queryKey: ["world-info-entry-detail", targetEntryId],
          exact: true,
        });
        return;
      }

      const detailQuery = queryClient.getQueryCache().find({
        queryKey: ["world-info-entry-detail", targetEntryId],
        exact: true,
      });
      if (detailQuery?.getObserversCount()) {
        queryClient.invalidateQueries({
          queryKey: ["world-info-entry-detail", targetEntryId],
          exact: true,
        });
      }
    },
    [queryClient],
  );

  const commitTranscriptState = useCallback((nextState: AgentTranscriptState) => {
    syncAgentTranscriptLiveState(transcriptStateRef.current, nextState);
    setMessages(nextState.messages);
    setStatus(nextState.status);
    setIsRunning(nextState.isRunning);
    setCurrentStage(nextState.currentStage);
  }, []);

  const updateTranscriptState = useCallback(
    (updater: (current: AgentTranscriptState) => AgentTranscriptState) => {
      const nextState = updater(transcriptStateRef.current);
      commitTranscriptState(nextState);
    },
    [commitTranscriptState],
  );

  const syncPendingMessageState = useCallback((nextPendingMessage: AgentPendingMessage | null) => {
    pendingMessageRef.current = nextPendingMessage;
    setPendingMessage(nextPendingMessage);
  }, []);

  const syncCompactingState = useCallback((nextIsCompacting: boolean) => {
    isCompactingRef.current = nextIsCompacting;
    setIsCompacting(nextIsCompacting);
  }, []);

  const handleEvent = useCallback(
    (event: AgentEvent) => {
      if (suppressSocketEventsAfterAbortRef.current && shouldSuppressAgentEventAfterAbort(event))
        return;
      transportRetryAttemptRef.current = 0;
      const payload = event.payload ?? {};
      const approvalId = typeof payload.approval_id === "string" ? payload.approval_id : "";
      if (
        event.type === "approval" &&
        approvalId &&
        ignoredApprovalIdsRef.current.has(approvalId)
      ) {
        return;
      }

      if (event.type === "pending_message") {
        const action = typeof payload.action === "string" ? payload.action : "";
        const messageId = typeof payload.message_id === "string" ? payload.message_id : "";
        const content = typeof payload.content === "string" ? payload.content : undefined;
        const createdAt = typeof payload.created_at === "string" ? payload.created_at : undefined;
        syncPendingMessageState(
          applyPendingUserMessageEvent(pendingMessageRef.current, {
            action: action as "queued" | "cancelled" | "consumed",
            messageId,
            content,
            createdAt,
          }),
        );
        return;
      }

      if (event.type === "compaction_error") {
        const message =
          event.content ||
          (typeof payload.message === "string" ? payload.message : "") ||
          i18n.t("assistant.compactionFailed");
        const trigger = typeof payload.trigger === "string" ? payload.trigger : "";
        const shouldToast = trigger !== "manual" || isCompactingRef.current;
        const shouldSuppressNextError = trigger !== "manual";
        suppressNextErrorAfterCompactionErrorRef.current = shouldSuppressNextError;
        syncCompactingState(false);
        if (shouldToast) {
          toast.error(`${i18n.t("assistant.compactionFailed")}：${message}`);
        }
        if (trigger === "manual") {
          const previousState = manualCompactionPreviousStateRef.current;
          manualCompactionPreviousStateRef.current = null;
          updateTranscriptState((current) =>
            restoreManualCompactionTranscriptState(
              current,
              previousState,
              typeof payload.session_id === "string"
                ? payload.session_id
                : (sessionIdRef.current ?? undefined),
            ),
          );
          return;
        }
        if (trigger !== "manual" || transcriptStateRef.current.isRunning) {
          updateTranscriptState((current) =>
            failCompactionTranscriptState(
              current,
              typeof payload.session_id === "string"
                ? payload.session_id
                : (sessionIdRef.current ?? undefined),
            ),
          );
        }
        return;
      }

      if (
        shouldSuppressAgentErrorAfterCompactionError(
          event,
          suppressNextErrorAfterCompactionErrorRef.current,
        )
      ) {
        suppressNextErrorAfterCompactionErrorRef.current = false;
        ignoredApprovalIdsRef.current.clear();
        updateTranscriptState((current) => ({
          ...current,
          status: "error",
          isRunning: false,
          currentStage: "",
        }));
        return;
      }

      const result = applyAgentTranscriptEventToLiveState(transcriptStateRef.current, event, {
        approvalPreviewFactory: createApprovalPreviewToolMessage,
        defaultRunningStage: AGENT_STAGE_TEXT.primary,
        fallbackAgent: "primary",
        getStageTextForAgent: getStageTextForAgentKey,
        getStageTextForStage: getStageTextForStageKey,
        keepRunningOnCompleted: hasRunningAsyncSubagent,
      });

      commitTranscriptState(result.state);

      if (event.type === "compaction") {
        syncCompactingState(event.status === "running");
        if (event.status !== "running" && event.payload?.trigger === "manual") {
          manualCompactionPreviousStateRef.current = null;
        }
      }

      if (event.display === "hidden") {
        if (event.type === "task_title_updated") {
          const taskId = typeof payload.task_id === "string" ? payload.task_id : "";
          const title = typeof payload.title === "string" ? payload.title : "";
          const updatedAt = typeof payload.updated_at === "string" ? payload.updated_at : undefined;
          if (taskId && title) onTaskTitleUpdated?.(taskId, title, updatedAt);
          return;
        }
        if (event.type === "token_usage") {
          const eventSessionId =
            typeof payload.session_id === "string" && payload.session_id
              ? payload.session_id
              : sessionIdRef.current;
          if (!eventSessionId) return;
          onTokenUsage?.(eventSessionId, {
            tokenInput: Number(payload.token_input ?? 0),
            tokenOutput: Number(payload.token_output ?? 0),
            tokenCache: Number(payload.token_cache ?? 0),
            contextInputTokens: Number(payload.context_input_tokens ?? 0),
            contextLength: Number(payload.context_length ?? 128000),
          });
          return;
        }
        if (event.type === "task_usage_snapshot") {
          const eventSessionId = typeof payload.session_id === "string" ? payload.session_id : "";
          const taskId = typeof payload.task_id === "string" ? payload.task_id : "";
          if (!eventSessionId || !taskId) return;
          onTaskUsageSnapshot?.({
            sessionId: eventSessionId,
            taskId,
            tokenInput: Number(payload.token_input ?? 0),
            tokenOutput: Number(payload.token_output ?? 0),
            tokenCache: Number(payload.token_cache ?? 0),
          });
          return;
        }
        if (event.type === "task_usage_delta") {
          const eventSessionId = typeof payload.session_id === "string" ? payload.session_id : "";
          const taskId = typeof payload.task_id === "string" ? payload.task_id : "";
          if (!eventSessionId || !taskId) return;
          onTaskUsageDelta?.({
            sessionId: eventSessionId,
            taskId,
            tokenInput: Number(payload.token_input ?? 0),
            tokenOutput: Number(payload.token_output ?? 0),
            tokenCache: Number(payload.token_cache ?? 0),
          });
          return;
        }
      }

      const message = result.message;
      if (message?.type === "chapter_refresh") {
        const targetChapterId =
          typeof message.payload?.chapter_id === "string" ? message.payload.chapter_id : undefined;
        invalidateChapterQueries(targetChapterId);
        return;
      }

      if (message?.type === "note_refresh") {
        const targetNoteId =
          typeof message.payload?.note_id === "string" ? message.payload.note_id : undefined;
        invalidateNoteQueries(targetNoteId);
        return;
      }

      if (message?.type === "error") {
        ignoredApprovalIdsRef.current.clear();
        toast.error(message.content || i18n.t("assistant.agentRunFailed"));
        return;
      }

      if (message?.type === "world_entry_refresh") {
        const targetWorldInfoId =
          typeof message.payload?.world_info_id === "string"
            ? message.payload.world_info_id
            : undefined;
        const targetEntryId =
          typeof message.payload?.entry_id === "string" ? message.payload.entry_id : undefined;
        const operation =
          typeof message.payload?.operation === "string" ? message.payload.operation : undefined;
        invalidateWorldEntryQueries(targetWorldInfoId, targetEntryId, operation);
        return;
      }

      if (message?.type === "completed" && result.state.status !== "running") {
        ignoredApprovalIdsRef.current.clear();
        invalidateChapterQueries();
        invalidateNoteQueries();
        invalidateWorldEntryQueries();
        return;
      }

      if (
        !result.message &&
        event.display !== "hidden" &&
        !["stage_start", "stage_transfer", "iteration_start"].includes(event.type)
      ) {
        console.warn("Unknown agent event type:", event.type);
      }
    },
    [
      commitTranscriptState,
      invalidateChapterQueries,
      invalidateNoteQueries,
      invalidateWorldEntryQueries,
      onTaskTitleUpdated,
      onTokenUsage,
      onTaskUsageDelta,
      onTaskUsageSnapshot,
      syncCompactingState,
      syncPendingMessageState,
      updateTranscriptState,
    ],
  );

  const attachAgentSocket = useCallback(
    (targetSessionId: string) => {
      socketUnsubscribeRef.current?.();
      socketUnsubscribeRef.current = subscribeAgentSessionEvents(
        targetSessionId,
        handleEvent,
        (error) => {
          if (
            transcriptStateRef.current.status === "idle" ||
            transcriptStateRef.current.status === "completed" ||
            transcriptStateRef.current.status === "error"
          ) {
            return;
          }
          transportRetryAttemptRef.current += 1;
          const next = applyTransportReconnectState({
            messages: transcriptStateRef.current.messages,
            error,
            attempt: transportRetryAttemptRef.current,
            currentStage: transcriptStateRef.current.currentStage,
            fallbackStage: getBestEffortContinueStage(transcriptStateRef.current.messages),
            preservedStatus: transcriptStateRef.current.status,
          });
          commitTranscriptState(next);
          if (transportRetryAttemptRef.current === 1) {
            toast.error(i18n.t("assistant.agentConnectionFailed", { error: error.message }));
          }
        },
      );
    },
    [commitTranscriptState, handleEvent],
  );

  const disconnectTransport = useCallback(() => {
    socketUnsubscribeRef.current?.();
    socketUnsubscribeRef.current = null;
  }, []);

  const reconnectTransport = useCallback(async () => {
    const activeSessionId = sessionIdRef.current ?? sessionId;
    if (!activeSessionId || socketUnsubscribeRef.current) return;

    const loadedState = getLoadedAgentSessionState({
      messages: transcriptStateRef.current.messages,
      isRemoteRunning:
        transcriptStateRef.current.status === "running" ||
        transcriptStateRef.current.status === "waiting_answer" ||
        transcriptStateRef.current.status === "waiting_approval",
    });
    if (!shouldJoinLoadedAgentSession(loadedState)) return;

    try {
      attachAgentSocket(activeSessionId);
      await joinAgentSession(activeSessionId);
    } catch (error) {
      transportRetryAttemptRef.current += 1;
      const normalizedError = error instanceof Error ? error : new Error(i18n.t("common.error"));
      const next = applyTransportReconnectState({
        messages: transcriptStateRef.current.messages,
        error: normalizedError,
        attempt: transportRetryAttemptRef.current,
        currentStage: transcriptStateRef.current.currentStage,
        fallbackStage: getBestEffortContinueStage(transcriptStateRef.current.messages),
        preservedStatus: loadedState.status,
      });
      commitTranscriptState(next);
      if (transportRetryAttemptRef.current === 1) {
        toast.error(i18n.t("assistant.agentConnectionFailed", { error: normalizedError.message }));
      }
    }
  }, [attachAgentSocket, commitTranscriptState, sessionId]);

  const startSession = useCallback(
    async (userRequest: string) => {
      if (!modelId) {
        toast.error(i18n.t("writing.aiSidebar.noModelSelected"));
        return;
      }

      try {
        suppressSocketEventsAfterAbortRef.current = false;
        transportRetryAttemptRef.current = 0;
        commitTranscriptState({
          messages: [createOptimisticUserMessage(userRequest)],
          status: "running",
          isRunning: true,
          currentStage: AGENT_STAGE_TEXT.primary,
        });

        const createResponse = await createAgentSession({
          project_id: projectId,
          model_id: modelId,
          ...(reasoningEffort ? { reasoning_effort: reasoningEffort } : {}),
          max_iterations: maxIterations,
          ...(agentKey ? { agent_key: agentKey } : {}),
        });

        onSessionCreated?.(createResponse);
        sessionIdRef.current = createResponse.session_id;
        activeModelIdRef.current = modelId;
        setSessionId(createResponse.session_id);
        queryClient.invalidateQueries({ queryKey: ["tasks", projectId], exact: false });
        attachAgentSocket(createResponse.session_id);
        await joinAgentSession(createResponse.session_id);
        await sendAgentMessage(createResponse.session_id, userRequest);
      } catch (error) {
        console.error("Failed to start agent session:", error);
        updateTranscriptState((current) => ({
          ...current,
          status: "error",
          isRunning: false,
          currentStage: "",
        }));
        toast.error(i18n.t("assistant.startFailed"));
      }
    },
    [
      attachAgentSocket,
      commitTranscriptState,
      maxIterations,
      modelId,
      onSessionCreated,
      projectId,
      queryClient,
      reasoningEffort,
      updateTranscriptState,
      agentKey,
    ],
  );

  const sendMessage = useCallback(
    async (message: string) => {
      const activeSessionId = sessionIdRef.current ?? sessionId;
      if (!activeSessionId) {
        toast.error(i18n.t("assistant.sessionNotFound"));
        return;
      }
      if (pendingMessageRef.current) {
        toast.error(i18n.t("writing.aiSidebar.cannotSendPendingMessage"));
        return;
      }

      try {
        suppressSocketEventsAfterAbortRef.current = false;
        transportRetryAttemptRef.current = 0;
        updateTranscriptState((current) => ({
          ...current,
          messages: current.messages.filter((item) => item.type !== "error"),
          status: "running",
          isRunning: true,
          currentStage: getBestEffortContinueStage(current.messages),
        }));

        if (!socketUnsubscribeRef.current) {
          attachAgentSocket(activeSessionId);
        }
        await joinAgentSession(activeSessionId);
        const nextModelId = modelId === activeModelIdRef.current ? undefined : modelId;
        const response = await sendAgentMessage(
          activeSessionId,
          message,
          nextModelId,
          reasoningEffort,
        );
        if (response.model_updated && nextModelId) activeModelIdRef.current = nextModelId;
        if (response.queued && response.pending_message) {
          syncPendingMessageState(createPendingUserMessage(response.pending_message));
        }
      } catch (error) {
        console.error("Failed to send message:", error);
        updateTranscriptState((current) => ({
          ...current,
          status: "error",
          isRunning: false,
          currentStage: "",
        }));
        toast.error(i18n.t("assistant.sendMessageFailed"));
      }
    },
    [
      attachAgentSocket,
      modelId,
      reasoningEffort,
      sessionId,
      syncPendingMessageState,
      updateTranscriptState,
    ],
  );

  const compactSession = useCallback(async () => {
    const activeSessionId = sessionIdRef.current ?? sessionId;
    if (!activeSessionId) {
      toast.error(i18n.t("assistant.sessionNotFound"));
      return false;
    }
    if (isCompactingRef.current) {
      toast.error(i18n.t("assistant.compactionRunning"));
      return false;
    }
    if (
      transcriptStateRef.current.status === "running" ||
      transcriptStateRef.current.status === "waiting_answer" ||
      transcriptStateRef.current.status === "waiting_approval"
    ) {
      toast.error(i18n.t("assistant.compactionRunningToast"));
      return false;
    }

    try {
      manualCompactionPreviousStateRef.current = {
        status: transcriptStateRef.current.status,
        isRunning: transcriptStateRef.current.isRunning,
        currentStage: transcriptStateRef.current.currentStage,
      };
      syncCompactingState(true);
      suppressSocketEventsAfterAbortRef.current = false;
      transportRetryAttemptRef.current = 0;
      if (!socketUnsubscribeRef.current) {
        attachAgentSocket(activeSessionId);
        await joinAgentSession(activeSessionId);
      }
      handleEvent({
        id: `compaction:manual:${activeSessionId}:pending`,
        correlation_id: `compaction:manual:${activeSessionId}:pending`,
        type: "compaction",
        role: "system",
        status: "running",
        display: "list",
        content: i18n.t("assistant.compactionRunning"),
        payload: {
          session_id: activeSessionId,
          trigger: "manual",
        },
      });
      const result = await compactAgentSession(activeSessionId);
      if (!result.success) {
        throw new Error(i18n.t("assistant.compactionFailed"));
      }
      handleEvent({
        id: `compaction:${result.compaction_id}`,
        correlation_id: `compaction:${result.compaction_id}`,
        type: "compaction",
        role: "system",
        status: "completed",
        display: "list",
        content: i18n.t("assistant.compactionDone"),
        payload: {
          session_id: result.session_id,
          compaction_id: result.compaction_id,
          trigger: "manual",
          start_seq: result.start_seq,
          end_seq: result.end_seq,
          source_input_tokens: result.source_input_tokens,
          summary_tokens: result.summary_tokens,
        },
      });
      return true;
    } catch (error) {
      console.error("Compaction failed:", error);
      const shouldToast = isCompactingRef.current;
      const previousState = manualCompactionPreviousStateRef.current;
      manualCompactionPreviousStateRef.current = null;
      syncCompactingState(false);
      updateTranscriptState((current) =>
        restoreManualCompactionTranscriptState(current, previousState, activeSessionId),
      );
      if (shouldToast) {
        toast.error(
          `${i18n.t("assistant.compactionFailed")}：${getAgentApiErrorMessage(error, i18n.t("assistant.compactionFailed"))}`,
        );
      }
      return false;
    }
  }, [attachAgentSocket, handleEvent, sessionId, syncCompactingState, updateTranscriptState]);

  const handleToolApproval = useCallback(
    async (approvalId: string, approved: boolean) => {
      if (!sessionId) {
        toast.error(i18n.t("assistant.sessionNotFound"));
        return;
      }
      try {
        console.debug("[agent:approval] click", { sessionId, approvalId, approved });
        suppressSocketEventsAfterAbortRef.current = false;
        ignoredApprovalIdsRef.current.add(approvalId);
        const nextMessages = removeApprovalMessageById(
          transcriptStateRef.current.messages,
          approvalId,
        );
        const hasPendingApproval = hasApprovalMessage(nextMessages);
        updateTranscriptState((current) => ({
          ...current,
          messages: nextMessages,
          status: hasPendingApproval ? "waiting_approval" : "running",
          isRunning: !hasPendingApproval,
          currentStage: hasPendingApproval ? "" : i18n.t("assistant.applyingChanges"),
        }));
        if (!socketUnsubscribeRef.current) {
          attachAgentSocket(sessionId);
          await joinAgentSession(sessionId);
        }
        await submitAgentToolApproval(sessionId, approvalId, approved);
      } catch (error) {
        console.error("Tool approval failed:", error);
        ignoredApprovalIdsRef.current.delete(approvalId);
        updateTranscriptState((current) => ({
          ...current,
          status: "error",
          isRunning: false,
          currentStage: "",
        }));
        toast.error(i18n.t("assistant.toolApprovalFailed"));
      }
    },
    [attachAgentSocket, sessionId, updateTranscriptState],
  );

  const submitQuestionAnswer = useCallback(
    async (actionId: string, answer: ClarificationAnswerItem[]) => {
      if (!sessionId) {
        toast.error(i18n.t("assistant.sessionNotFound"));
        return;
      }
      if (!actionId) {
        toast.error(i18n.t("assistant.clarificationNotFound"));
        return;
      }

      try {
        suppressSocketEventsAfterAbortRef.current = false;
        updateTranscriptState((current) => ({
          ...current,
          messages: current.messages.filter(
            (item) =>
              item.type !== "question" && item.type !== "clarification" && item.type !== "error",
          ),
          status: "running",
          isRunning: true,
          currentStage: getBestEffortContinueStage(current.messages),
        }));
        if (!socketUnsubscribeRef.current) {
          attachAgentSocket(sessionId);
          await joinAgentSession(sessionId);
        }
        await submitAgentQuestionAnswer(sessionId, actionId, answer);
      } catch (error) {
        console.error("Question answer failed:", error);
        updateTranscriptState((current) => ({
          ...current,
          status: "error",
          isRunning: false,
          currentStage: "",
        }));
        toast.error(i18n.t("assistant.submitAnswerFailed"));
      }
    },
    [attachAgentSocket, sessionId, updateTranscriptState],
  );

  const resetSession = useCallback(() => {
    sessionIdRef.current = null;
    activeModelIdRef.current = null;
    suppressSocketEventsAfterAbortRef.current = false;
    transportRetryAttemptRef.current = 0;
    suppressNextErrorAfterCompactionErrorRef.current = false;
    syncPendingMessageState(null);
    syncCompactingState(false);
    setSessionId(null);
    commitTranscriptState(createAgentTranscriptLiveState());
    socketUnsubscribeRef.current?.();
    socketUnsubscribeRef.current = null;
  }, [commitTranscriptState, syncCompactingState, syncPendingMessageState]);

  const abortSession = useCallback(async () => {
    const activeSessionId = sessionId;
    suppressSocketEventsAfterAbortRef.current = true;
    transportRetryAttemptRef.current = 0;
    suppressNextErrorAfterCompactionErrorRef.current = false;
    socketUnsubscribeRef.current?.();
    socketUnsubscribeRef.current = null;
    syncPendingMessageState(null);
    syncCompactingState(false);
    updateTranscriptState((current) =>
      abortCompactionTranscriptState(
        {
          ...current,
          messages: clearRetryMessages(cancelStreamingAgentMessages(current.messages)),
        },
        activeSessionId ?? undefined,
      ),
    );

    if (activeSessionId) {
      try {
        await cancelAgentSession(activeSessionId);
      } catch (error) {
        console.error("Failed to cancel agent session:", error);
      }
    }
  }, [sessionId, syncCompactingState, syncPendingMessageState, updateTranscriptState]);

  const loadSession = useCallback(
    (
      existingSessionId: string,
      existingMessages: AgentMessage[],
      options: {
        reconnect?: boolean;
        isRemoteRunning?: boolean;
      } = {},
    ) => {
      sessionIdRef.current = existingSessionId;
      activeModelIdRef.current = null;
      suppressSocketEventsAfterAbortRef.current = false;
      transportRetryAttemptRef.current = 0;
      suppressNextErrorAfterCompactionErrorRef.current = false;
      syncPendingMessageState(null);
      syncCompactingState(false);
      setSessionId(existingSessionId);
      socketUnsubscribeRef.current?.();
      socketUnsubscribeRef.current = null;

      const loadedState = getLoadedAgentSessionState({
        messages: existingMessages,
        isRemoteRunning: options.isRemoteRunning,
      });
      commitTranscriptState({
        messages: existingMessages,
        status: loadedState.status,
        isRunning: loadedState.isRunning,
        currentStage: loadedState.currentStage,
      });

      if (options.reconnect && shouldJoinLoadedAgentSession(loadedState)) {
        attachAgentSocket(existingSessionId);
        void joinAgentSession(existingSessionId).catch((error) => {
          transportRetryAttemptRef.current += 1;
          const normalizedError =
            error instanceof Error ? error : new Error(i18n.t("common.error"));
          const next = applyTransportReconnectState({
            messages: transcriptStateRef.current.messages,
            error: normalizedError,
            attempt: transportRetryAttemptRef.current,
            currentStage: transcriptStateRef.current.currentStage,
            fallbackStage: getBestEffortContinueStage(transcriptStateRef.current.messages),
            preservedStatus: loadedState.status,
          });
          commitTranscriptState(next);
          if (transportRetryAttemptRef.current === 1) {
            toast.error(
              i18n.t("assistant.agentConnectionFailed", { error: normalizedError.message }),
            );
          }
        });
      }
    },
    [attachAgentSocket, commitTranscriptState, syncCompactingState, syncPendingMessageState],
  );

  const cancelPendingMessage = useCallback(async (): Promise<string | null> => {
    const activeSessionId = sessionIdRef.current ?? sessionId;
    const activePendingMessage = pendingMessageRef.current;
    if (!activeSessionId || !activePendingMessage) return null;

    try {
      const result = await cancelPendingAgentMessage(
        activeSessionId,
        activePendingMessage.messageId,
      );
      syncPendingMessageState(null);
      return result.restored_message_content;
    } catch (error) {
      console.error("Failed to cancel pending agent message:", error);
      if (pendingMessageRef.current?.messageId !== activePendingMessage.messageId) {
        return null;
      }
      toast.error(i18n.t("assistant.cancelPendingFailed"));
      return null;
    }
  }, [sessionId, syncPendingMessageState]);

  const rollbackToRevision = useCallback(
    async (messageId: string): Promise<string | null> => {
      if (!sessionId || isRollbacking || isRunning || isCompactingRef.current) {
        toast.error(i18n.t("assistant.rollbackImpossible"));
        return null;
      }

      const targetMessage = messages.find((m) => m.id === messageId);
      if (!isUserTextMessage(targetMessage)) {
        toast.error(i18n.t("assistant.rollbackOnlyUserMessage"));
        return null;
      }

      if (!targetMessage.revisionId) {
        toast.error(i18n.t("assistant.rollbackNoRevision"));
        return null;
      }

      setIsRollbacking(true);

      try {
        const result = await rollbackAgentRevision(sessionId, targetMessage.revisionId);

        if (result.success) {
          const targetIndex = messages.findIndex((m) => m.id === messageId);
          commitTranscriptState({
            messages: messages.slice(0, targetIndex),
            status: "idle",
            isRunning: false,
            currentStage: "",
          });

          invalidateChapterQueries();
          invalidateNoteQueries();
          invalidateWorldEntryQueries();

          toast.success(i18n.t("assistant.rollbackSuccess"));

          return result.restored_message_content;
        } else {
          toast.error(i18n.t("assistant.rollbackFailed"));
          return null;
        }
      } catch (error) {
        console.error("Rollback failed:", error);
        toast.error(i18n.t("assistant.rollbackFailed"));
        return null;
      } finally {
        setIsRollbacking(false);
      }
    },
    [
      commitTranscriptState,
      sessionId,
      isRollbacking,
      isRunning,
      messages,
      invalidateChapterQueries,
      invalidateNoteQueries,
      invalidateWorldEntryQueries,
    ],
  );

  const forkFromRevision = useCallback(
    async (sourceRevisionId: string): Promise<AgentForkResponse | null> => {
      const activeSessionId = sessionIdRef.current ?? sessionId;
      if (!activeSessionId || isRollbacking || isRunning || isCompactingRef.current) {
        toast.error(i18n.t("assistant.forkImpossible"));
        return null;
      }
      if (!sourceRevisionId) {
        toast.error(i18n.t("assistant.forkNoRevision"));
        return null;
      }
      if (!modelId) {
        toast.error(i18n.t("writing.aiSidebar.noModelSelected"));
        return null;
      }

      try {
        const result = await forkAgentSession(activeSessionId, sourceRevisionId, modelId);
        queryClient.invalidateQueries({ queryKey: ["tasks", projectId], exact: false });
        toast.success(i18n.t("assistant.forkSuccess"));
        return result;
      } catch (error) {
        console.error("Fork failed:", error);
        toast.error(i18n.t("assistant.forkFailed"));
        return null;
      }
    },
    [isRollbacking, isRunning, modelId, projectId, queryClient, sessionId],
  );

  return {
    sessionId,
    messages,
    pendingMessage,
    status,
    isRunning,
    isCompacting,
    isRollbacking,
    currentStage,
    startSession,
    sendMessage,
    resetSession,
    loadSession,
    disconnectTransport,
    reconnectTransport,
    compactSession,
    cancelPendingMessage,
    rollbackToRevision,
    forkFromRevision,
    handleToolApproval,
    submitQuestionAnswer,
    abortSession,
  };
}
