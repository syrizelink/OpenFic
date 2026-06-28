/**
 * Agent Hook
 *
 * Agent 会话管理 Hook
 */

import { useState, useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "@/components";
import { joinAgentSession, subscribeAgentSessionEvents } from "../lib/agent-socket";
import { createApprovalPreviewToolMessage } from "../lib/chapter-tool-preview";
import { clearRetryMessages } from "../lib/retry-message-state";
import {
  abortCompactionTranscriptState,
  failCompactionTranscriptState,
  getStageTextForAgentKey,
  getStageTextForStageKey,
  restoreManualCompactionTranscriptState,
  type AgentTranscriptState,
} from "../lib/agent-transcript-state";
import {
  applyAgentTranscriptEventToLiveState,
  createAgentTranscriptLiveState,
  syncAgentTranscriptLiveState,
} from "../lib/agent-transcript-live-state";
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
import { applyTransportReconnectState } from "./agent-session-transport-state";

import type {
  AgentMessage,
  AgentPendingMessage,
  AgentSessionCreateResponse,
  AgentSessionStatus,
  AgentEvent,
} from "@/lib/agent.types";
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
import type { TokenUsageState } from "@/lib/agent.types";
import type { AgentForkResponse } from "@/lib/agent.types";
import {
  applyPendingUserMessageEvent,
  createPendingUserMessage,
} from "../lib/pending-user-message-state";

function isUserTextMessage(message: AgentMessage | undefined): message is AgentMessage {
  return Boolean(message && (message.type === "user_request" || (message.type === "text" && message.role === "user")));
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
    (message) => (message.type === "approval" || message.type === "tool_approval")
      && Boolean(message.toolApproval?.approval_id)
  );
}

function removeApprovalMessageById(
  messages: AgentMessage[],
  approvalId: string
): AgentMessage[] {
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
      getString(responseData.message)
      || detailMessage
      || getString(responseData.detail)
      || getString(responseData.reason)
      || getString(responseData.error)
      || fallback
    );
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

interface UseAgentSessionOptions {
  projectId: string;
  modelId: string;
  agentKey?: string;
  maxIterations?: number;
  onTokenUsage?: (sessionId: string, usage: TokenUsageState) => void;
  onTaskUsageSnapshot?: (
    payload: {
      sessionId: string;
      taskId: string;
      tokenInput: number;
      tokenOutput: number;
      tokenCache: number;
    }
  ) => void;
  onTaskUsageDelta?: (
    payload: {
      sessionId: string;
      taskId: string;
      tokenInput: number;
      tokenOutput: number;
      tokenCache: number;
    }
  ) => void;
  onTaskTitleUpdated?: (taskId: string, title: string, updatedAt?: string) => void;
  onSessionCreated?: (session: AgentSessionCreateResponse) => void;
}

export function useAgentSession({
  projectId,
  modelId,
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
  const pendingMessageRef = useRef<AgentPendingMessage | null>(null);
  const isCompactingRef = useRef(false);
  const manualCompactionPreviousStateRef = useRef<Pick<AgentTranscriptState, "status" | "isRunning" | "currentStage"> | null>(null);
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
    [projectId, queryClient]
  );

  const invalidateNoteQueries = useCallback(
    (targetNoteId?: string) => {
      queryClient.invalidateQueries({ queryKey: ["note-tree", projectId] });
      if (targetNoteId) {
        queryClient.invalidateQueries({ queryKey: ["note", targetNoteId] });
      }
    },
    [projectId, queryClient]
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
    [commitTranscriptState]
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
      if (suppressSocketEventsAfterAbortRef.current && shouldSuppressAgentEventAfterAbort(event)) return;
      transportRetryAttemptRef.current = 0;
      const payload = event.payload ?? {};
      const approvalId = typeof payload.approval_id === "string" ? payload.approval_id : "";
      if (event.type === "approval" && approvalId && ignoredApprovalIdsRef.current.has(approvalId)) {
        return;
      }

      if (event.type === "pending_message") {
        const action = typeof payload.action === "string" ? payload.action : "";
        const messageId = typeof payload.message_id === "string" ? payload.message_id : "";
        const content = typeof payload.content === "string" ? payload.content : undefined;
        const createdAt = typeof payload.created_at === "string" ? payload.created_at : undefined;
        syncPendingMessageState(
          applyPendingUserMessageEvent(
            pendingMessageRef.current,
            {
              action: action as "queued" | "cancelled" | "consumed",
              messageId,
              content,
              createdAt,
            },
          ),
        );
        return;
      }

      if (event.type === "compaction_error") {
        const message = event.content || (typeof payload.message === "string" ? payload.message : "") || "压缩失败";
        const trigger = typeof payload.trigger === "string" ? payload.trigger : "";
        const shouldToast = trigger !== "manual" || isCompactingRef.current;
        const shouldSuppressNextError = trigger !== "manual";
        suppressNextErrorAfterCompactionErrorRef.current = shouldSuppressNextError;
        syncCompactingState(false);
        if (shouldToast) {
          toast.error(`压缩失败：${message}`);
        }
        if (trigger === "manual") {
          const previousState = manualCompactionPreviousStateRef.current;
          manualCompactionPreviousStateRef.current = null;
          updateTranscriptState((current) => restoreManualCompactionTranscriptState(
            current,
            previousState,
            typeof payload.session_id === "string" ? payload.session_id : sessionIdRef.current ?? undefined
          ));
          return;
        }
        if (trigger !== "manual" || transcriptStateRef.current.isRunning) {
          updateTranscriptState((current) => failCompactionTranscriptState(
            current,
            typeof payload.session_id === "string" ? payload.session_id : sessionIdRef.current ?? undefined
          ));
        }
        return;
      }

      if (
        shouldSuppressAgentErrorAfterCompactionError(
          event,
          suppressNextErrorAfterCompactionErrorRef.current
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

      const result = applyAgentTranscriptEventToLiveState(
        transcriptStateRef.current,
        event,
        {
          approvalPreviewFactory: createApprovalPreviewToolMessage,
          defaultRunningStage: AGENT_STAGE_TEXT.primary,
          fallbackAgent: "primary",
          getStageTextForAgent: getStageTextForAgentKey,
          getStageTextForStage: getStageTextForStageKey,
          keepRunningOnCompleted: hasRunningAsyncSubagent,
        }
      );

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
          const eventSessionId = typeof payload.session_id === "string" && payload.session_id
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
        const targetChapterId = typeof message.payload?.chapter_id === "string"
          ? message.payload.chapter_id
          : undefined;
        invalidateChapterQueries(targetChapterId);
        return;
      }

      if (message?.type === "note_refresh") {
        const targetNoteId = typeof message.payload?.note_id === "string"
          ? message.payload.note_id
          : undefined;
        invalidateNoteQueries(targetNoteId);
        return;
      }

      if (message?.type === "error") {
        ignoredApprovalIdsRef.current.clear();
        toast.error(message.content || "Agent 运行失败");
        return;
      }

if (message?.type === "completed" && result.state.status !== "running") {
        ignoredApprovalIdsRef.current.clear();
        invalidateChapterQueries();
        invalidateNoteQueries();
        return;
      }

      if (
        !result.message
        && event.display !== "hidden"
        && !["stage_start", "stage_transfer", "iteration_start"].includes(event.type)
      ) {
        console.warn("Unknown agent event type:", event.type);
      }
    },
    [
      commitTranscriptState,
      invalidateChapterQueries,
      invalidateNoteQueries,
      onTaskTitleUpdated,
      onTokenUsage,
      onTaskUsageDelta,
      onTaskUsageSnapshot,
      syncCompactingState,
      syncPendingMessageState,
      updateTranscriptState,
    ]
  );

  const attachAgentSocket = useCallback(
    (targetSessionId: string) => {
      socketUnsubscribeRef.current?.();
      socketUnsubscribeRef.current = subscribeAgentSessionEvents(
        targetSessionId,
        handleEvent,
        (error) => {
          if (
            transcriptStateRef.current.status === "idle"
            || transcriptStateRef.current.status === "completed"
            || transcriptStateRef.current.status === "error"
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
            toast.error(`Agent 连接失败：${error.message}`);
          }
        }
      );
    },
    [commitTranscriptState, handleEvent]
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
        transcriptStateRef.current.status === "running"
        || transcriptStateRef.current.status === "waiting_answer"
        || transcriptStateRef.current.status === "waiting_approval",
    });
    if (!shouldJoinLoadedAgentSession(loadedState)) return;

    try {
      attachAgentSocket(activeSessionId);
      await joinAgentSession(activeSessionId);
    } catch (error) {
      transportRetryAttemptRef.current += 1;
      const normalizedError = error instanceof Error ? error : new Error("未知错误");
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
        toast.error(`Agent 连接失败：${normalizedError.message}`);
      }
    }
  }, [attachAgentSocket, commitTranscriptState, sessionId]);

const startSession = useCallback(
    async (userRequest: string) => {
      if (!modelId) {
        toast.error("请先选择模型");
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
          max_iterations: maxIterations,
          ...(agentKey ? { agent_key: agentKey } : {}),
        });

        onSessionCreated?.(createResponse);
        sessionIdRef.current = createResponse.session_id;
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
        toast.error("启动 Agent 失败");
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
      updateTranscriptState,
      agentKey,
    ]
  );

  const sendMessage = useCallback(
    async (message: string) => {
      const activeSessionId = sessionIdRef.current ?? sessionId;
      if (!activeSessionId) {
        toast.error("会话不存在");
        return;
      }
      if (pendingMessageRef.current) {
        toast.error("请先处理待发送消息");
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
          await joinAgentSession(activeSessionId);
        }
        const response = await sendAgentMessage(activeSessionId, message);
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
        toast.error("发送消息失败");
      }
    },
    [attachAgentSocket, sessionId, syncPendingMessageState, updateTranscriptState]
  );

  const compactSession = useCallback(async () => {
    const activeSessionId = sessionIdRef.current ?? sessionId;
    if (!activeSessionId) {
      toast.error("会话不存在");
      return false;
    }
    if (isCompactingRef.current) {
      toast.error("正在压缩上下文");
      return false;
    }
    if (
      transcriptStateRef.current.status === "running"
      || transcriptStateRef.current.status === "waiting_answer"
      || transcriptStateRef.current.status === "waiting_approval"
    ) {
      toast.error("Agent运行中，无法手动压缩");
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
        content: "正在压缩上下文",
        payload: {
          session_id: activeSessionId,
          trigger: "manual",
        },
      });
      const result = await compactAgentSession(activeSessionId);
      if (!result.success) {
        throw new Error("压缩失败");
      }
      handleEvent({
        id: `compaction:${result.compaction_id}`,
        correlation_id: `compaction:${result.compaction_id}`,
        type: "compaction",
        role: "system",
        status: "completed",
        display: "list",
        content: "上下文已压缩",
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
      updateTranscriptState((current) => restoreManualCompactionTranscriptState(
        current,
        previousState,
        activeSessionId
      ));
      if (shouldToast) {
        toast.error(`压缩失败：${getAgentApiErrorMessage(error, "压缩失败")}`);
      }
      return false;
    }
  }, [attachAgentSocket, handleEvent, sessionId, syncCompactingState, updateTranscriptState]);

  const handleToolApproval = useCallback(
    async (approvalId: string, approved: boolean) => {
      if (!sessionId) {
        toast.error("会话不存在");
        return;
      }
      try {
        console.debug("[agent:approval] click", { sessionId, approvalId, approved });
        suppressSocketEventsAfterAbortRef.current = false;
        ignoredApprovalIdsRef.current.add(approvalId);
        const nextMessages = removeApprovalMessageById(transcriptStateRef.current.messages, approvalId);
        const hasPendingApproval = hasApprovalMessage(nextMessages);
        updateTranscriptState((current) => ({
          ...current,
          messages: nextMessages,
          status: hasPendingApproval ? "waiting_approval" : "running",
          isRunning: !hasPendingApproval,
          currentStage: hasPendingApproval ? "" : "正在应用修改...",
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
        toast.error("工具审批失败");
      }
    },
    [attachAgentSocket, sessionId, updateTranscriptState]
  );

  const submitQuestionAnswer = useCallback(
    async (actionId: string, answer: string) => {
      if (!sessionId) {
        toast.error("会话不存在");
        return;
      }
      if (!actionId) {
        toast.error("澄清请求不存在");
        return;
      }

      try {
        suppressSocketEventsAfterAbortRef.current = false;
        updateTranscriptState((current) => ({
          ...current,
          messages: current.messages.filter((item) => item.type !== "question" && item.type !== "clarification" && item.type !== "error"),
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
        toast.error("提交回答失败");
      }
    },
    [attachAgentSocket, sessionId, updateTranscriptState]
  );

  const resetSession = useCallback(() => {
    sessionIdRef.current = null;
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
    updateTranscriptState((current) => abortCompactionTranscriptState(
      {
        ...current,
        messages: clearRetryMessages(cancelStreamingAgentMessages(current.messages)),
      },
      activeSessionId ?? undefined
    ));

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
      } = {}
    ) => {
      sessionIdRef.current = existingSessionId;
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
          const normalizedError = error instanceof Error ? error : new Error("未知错误");
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
            toast.error(`Agent 连接失败：${normalizedError.message}`);
          }
        });
      }
    },
    [attachAgentSocket, commitTranscriptState, syncCompactingState, syncPendingMessageState]
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
      toast.error("取消待发送消息失败");
      return null;
    }
  }, [sessionId, syncPendingMessageState]);

  const rollbackToRevision = useCallback(
    async (messageId: string): Promise<string | null> => {
      if (!sessionId || isRollbacking || isRunning || isCompactingRef.current) {
        toast.error("无法执行回滚操作");
        return null;
      }

      const targetMessage = messages.find((m) => m.id === messageId);
      if (!isUserTextMessage(targetMessage)) {
        toast.error("只能回滚到用户消息节点");
        return null;
      }

      if (!targetMessage.revisionId) {
        toast.error("该消息节点没有revision信息");
        return null;
      }

      setIsRollbacking(true);

      try {
        const result = await rollbackAgentRevision(
          sessionId,
          targetMessage.revisionId
        );

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

          toast.success("已回滚到该消息发送前的状态");

          return result.restored_message_content;
        } else {
          toast.error("回滚失败");
          return null;
        }
      } catch (error) {
        console.error("Rollback failed:", error);
        toast.error("回滚操作失败");
        return null;
      } finally {
        setIsRollbacking(false);
      }
    },
    [commitTranscriptState, sessionId, isRollbacking, isRunning, messages, invalidateChapterQueries, invalidateNoteQueries]
  );

  const forkFromRevision = useCallback(
    async (sourceRevisionId: string): Promise<AgentForkResponse | null> => {
      const activeSessionId = sessionIdRef.current ?? sessionId;
      if (!activeSessionId || isRollbacking || isRunning || isCompactingRef.current) {
        toast.error("无法执行分叉操作");
        return null;
      }
      if (!sourceRevisionId) {
        toast.error("该消息节点没有revision信息，无法分叉");
        return null;
      }
      if (!modelId) {
        toast.error("请先选择一个模型");
        return null;
      }

      try {
        const result = await forkAgentSession(activeSessionId, sourceRevisionId, modelId);
        queryClient.invalidateQueries({ queryKey: ["tasks", projectId], exact: false });
        toast.success("已创建分叉任务");
        return result;
      } catch (error) {
        console.error("Fork failed:", error);
        toast.error("分叉任务创建失败");
        return null;
      }
    },
    [isRollbacking, isRunning, modelId, projectId, queryClient, sessionId]
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
