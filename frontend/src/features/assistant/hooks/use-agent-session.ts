/**
 * Agent Hook
 *
 * Agent 会话管理 Hook
 */

import { useQueryClient } from "@tanstack/react-query";
import { useState, useCallback, useEffect, useRef } from "react";

import { toast } from "@/components";
import { useCharactersStore } from "@/features/characters/store/use-characters-store";
import { useWorldInfoStore } from "@/features/world-info/store/use-world-info-store";
import { invalidateWritingEditorEntityQueries } from "@/features/writing/hooks/use-writing-editor-entity";
import { useTabsStore } from "@/features/writing/store/use-tabs-store";
import i18n from "@/i18n";
import type {
  AgentImageAttachment,
  AgentMessage,
  AgentPendingMessage,
  AgentSessionCreateResponse,
  AgentSessionStatus,
  AgentEvent,
  ClarificationQuestion,
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
  submitAgentInterruptBatch,
  rollbackAgentRevision,
  cancelAgentSession,
  uploadAgentImageAttachment,
  submitAgentToolApproval,
} from "@/lib/api-client";
import type { CharacterListResponse } from "@/lib/character.types";
import type { WorldInfoEntryBriefListResponse } from "@/lib/world-info.types";

import type { ClarificationAnswerItem } from "../components/agent/message-blocks/messages/special/clarification-flow-state";
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
import { removeListItemFromCache } from "../lib/entity-list-cache";
import {
  applyPendingUserMessageEvent,
  createPendingUserMessage,
} from "../lib/pending-user-message-state";
import { clearRetryMessages } from "../lib/retry-message-state";
import {
  createStreamingDeltaCoalescer,
  isStreamingDeltaEvent,
} from "../lib/streaming-delta-coalescer";
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

interface RollbackInputRestore {
  content: string;
  attachments: AgentImageAttachment[];
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

function clearPendingInterruptMessages(messages: AgentMessage[]): AgentMessage[] {
  return messages.filter((message) => {
    if (
      message.type !== "approval" &&
      message.type !== "tool_approval" &&
      message.type !== "question" &&
      message.type !== "clarification"
    ) {
      return true;
    }
    return (
      message.status !== undefined && message.status !== "pending" && message.status !== "running"
    );
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

function buildPendingInterruptMessages(interrupts: Record<string, unknown>[]): AgentMessage[] {
  const restoredBatchId =
    interrupts.length > 1 ? `restored-interrupt-batch-${Date.now()}` : undefined;
  return interrupts.flatMap((interrupt, index): AgentMessage[] => {
    const interruptId = getString(interrupt.interrupt_id) || getString(interrupt.id);
    if (!interruptId) return [];
    const timestamp = Date.now() + index;
    const batchFields = {
      interruptBatchId: getString(interrupt.batch_id) || restoredBatchId,
      interruptBatchIndex:
        typeof interrupt.batch_index === "number" ? interrupt.batch_index : index,
      interruptBatchTotal:
        typeof interrupt.batch_total === "number" ? interrupt.batch_total : interrupts.length,
    };
    if (interrupt.type === "ask_user") {
      const questions = Array.isArray(interrupt.questions)
        ? (interrupt.questions as ClarificationQuestion[])
        : [];
      return [
        {
          id: interruptId,
          type: "question",
          role: "system",
          status: "pending",
          display: "panel",
          timestamp,
          questions,
          payload: { action_id: interruptId, questions, ...batchFields },
          correlationId: interruptId,
          ...batchFields,
        },
      ];
    }
    if (interrupt.type !== "tool_approval") return [];
    const toolName = getString(interrupt.tool_name) || "";
    const toolArgs = isRecord(interrupt.args)
      ? interrupt.args
      : isRecord(interrupt.tool_args)
        ? interrupt.tool_args
        : {};
    const approvalId = getString(interrupt.approval_id) || interruptId;
    const toolResultPreview = isRecord(interrupt.tool_result_preview)
      ? interrupt.tool_result_preview
      : undefined;
    return [
      {
        id: interruptId,
        type: "approval",
        role: "system",
        status: "pending",
        display: "panel",
        timestamp,
        toolApproval: {
          approval_id: approvalId,
          tool_name: toolName,
          tool_args: toolArgs,
          tool_call_id: getString(interrupt.tool_call_id),
          tool_result_preview: toolResultPreview,
          message:
            getString(interrupt.message) ||
            i18n.t("assistant.tools.toolApprovalQuestion", { toolName }),
          interrupt_behavior: interrupt.interrupt_behavior === "block" ? "block" : "cancel",
        },
        payload: {
          approval_id: approvalId,
          tool_name: toolName,
          tool_args: toolArgs,
          tool_call_id: getString(interrupt.tool_call_id),
          tool_result_preview: toolResultPreview,
          ...batchFields,
        },
        correlationId: interruptId,
        ...batchFields,
      },
    ];
  });
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
    cost: number;
  }) => void;
  onTaskUsageDelta?: (payload: {
    sessionId: string;
    taskId: string;
    tokenInput: number;
    tokenOutput: number;
    tokenCache: number;
    cost: number;
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
  const interruptBatchRef = useRef<{
    batchId: string;
    panels: AgentMessage[];
    decisions: Record<string, Record<string, unknown>>;
  } | null>(null);
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
  const projectIdRef = useRef(projectId);
  projectIdRef.current = projectId;
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
      deltaCoalescerRef.current?.dispose();
      deltaCoalescerRef.current = null;
    };
  }, []);

  const invalidateChapterQueries = useCallback(
    (targetChapterId?: string, operation?: string) => {
      queryClient.invalidateQueries({ queryKey: ["volume-tree", projectId] });
      if (operation === "delete") {
        if (targetChapterId) {
          void queryClient.cancelQueries({
            queryKey: ["chapter", targetChapterId],
            exact: true,
          });
        }
        queryClient.invalidateQueries({ queryKey: ["projects"] });
        return;
      }
      if (targetChapterId) {
        queryClient.invalidateQueries({ queryKey: ["chapter", targetChapterId] });
      }
      invalidateWritingEditorEntityQueries(queryClient, "chapter", targetChapterId);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    [projectId, queryClient],
  );

  const invalidateNoteQueries = useCallback(
    (targetNoteId?: string, operation?: string) => {
      queryClient.invalidateQueries({ queryKey: ["note-tree", projectId] });
      if (operation === "delete") return;

      if (targetNoteId) {
        queryClient.invalidateQueries({ queryKey: ["note", targetNoteId] });
      }
      invalidateWritingEditorEntityQueries(queryClient, "note", targetNoteId);
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
        void queryClient.cancelQueries({
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

  const invalidateCharacterQueries = useCallback(
    (targetCharacterId?: string, operation?: string) => {
      queryClient.invalidateQueries({ queryKey: ["characters", projectId] });
      if (!targetCharacterId) return;

      if (operation === "delete") {
        void queryClient.cancelQueries({
          queryKey: ["character", targetCharacterId],
        });
        return;
      }

      queryClient.invalidateQueries({
        queryKey: ["character", targetCharacterId],
      });
    },
    [projectId, queryClient],
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

  const applyTranscriptEvent = useCallback(
    (event: AgentEvent) => {
      const result = applyAgentTranscriptEventToLiveState(transcriptStateRef.current, event, {
        approvalPreviewFactory: createApprovalPreviewToolMessage,
        defaultRunningStage: agentKey || AGENT_STAGE_TEXT.build,
        fallbackAgent: agentKey || "build",
        getStageTextForAgent: getStageTextForAgentKey,
        getStageTextForStage: getStageTextForStageKey,
        keepRunningOnCompleted: hasRunningAsyncSubagent,
      });
      commitTranscriptState(result.state);
      return result;
    },
    [agentKey, commitTranscriptState],
  );

  const applyTranscriptEventRef = useRef(applyTranscriptEvent);
  applyTranscriptEventRef.current = applyTranscriptEvent;

  const deltaCoalescerRef = useRef<ReturnType<typeof createStreamingDeltaCoalescer> | null>(null);
  if (deltaCoalescerRef.current === null) {
    deltaCoalescerRef.current = createStreamingDeltaCoalescer((events) => {
      for (const event of events) {
        applyTranscriptEventRef.current(event);
      }
    });
  }

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

      if (isStreamingDeltaEvent(event)) {
        deltaCoalescerRef.current?.push(event);
        return;
      }
      deltaCoalescerRef.current?.flush();

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

      const result = applyTranscriptEvent(event);
      const message = result.message;

      if (message?.interruptBatchId && typeof message.interruptBatchTotal === "number") {
        const batchId = message.interruptBatchId;
        const batchMessages = transcriptStateRef.current.messages
          .filter((item) => item.interruptBatchId === batchId)
          .sort(
            (left, right) => (left.interruptBatchIndex ?? 0) - (right.interruptBatchIndex ?? 0),
          );
        interruptBatchRef.current = {
          batchId,
          panels: batchMessages,
          decisions:
            interruptBatchRef.current?.batchId === batchId
              ? interruptBatchRef.current.decisions
              : {},
        };
      }

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
            cost: Number(payload.cost ?? 0),
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
            cost: Number(payload.cost ?? 0),
          });
          return;
        }
      }

      if (message?.type === "chapter_refresh") {
        const targetChapterId =
          typeof message.payload?.chapter_id === "string" ? message.payload.chapter_id : undefined;
        const operation =
          typeof message.payload?.operation === "string" ? message.payload.operation : undefined;
        if (operation === "delete" && targetChapterId) {
          useTabsStore.getState().removeTabsByReference("chapter", targetChapterId);
        }
        invalidateChapterQueries(targetChapterId, operation);
        return;
      }

      if (message?.type === "note_refresh") {
        const targetNoteId =
          typeof message.payload?.note_id === "string" ? message.payload.note_id : undefined;
        const operation =
          typeof message.payload?.operation === "string" ? message.payload.operation : undefined;
        if (operation === "delete" && targetNoteId) {
          useTabsStore.getState().removeTabsByReference("note", targetNoteId);
        }
        invalidateNoteQueries(targetNoteId, operation);
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
        if (
          operation === "delete" &&
          targetEntryId &&
          useWorldInfoStore.getState().currentEntryId === targetEntryId
        ) {
          if (targetWorldInfoId) {
            queryClient.setQueryData(
              ["world-info-entries", targetWorldInfoId],
              (data: WorldInfoEntryBriefListResponse | undefined) =>
                removeListItemFromCache(data, targetEntryId),
            );
          }
          useWorldInfoStore.getState().setCurrentEntry(null);
        }
        invalidateWorldEntryQueries(targetWorldInfoId, targetEntryId, operation);
        return;
      }

      if (message?.type === "character_refresh") {
        const targetCharacterId =
          typeof message.payload?.character_id === "string"
            ? message.payload.character_id
            : undefined;
        const operation =
          typeof message.payload?.operation === "string" ? message.payload.operation : undefined;
        if (
          operation === "delete" &&
          targetCharacterId &&
          useCharactersStore.getState().currentCharacterId === targetCharacterId
        ) {
          queryClient.setQueryData(
            ["characters", projectId],
            (data: CharacterListResponse | undefined) =>
              removeListItemFromCache(data, targetCharacterId),
          );
          useCharactersStore.getState().setCurrentCharacter(null);
        }
        invalidateCharacterQueries(targetCharacterId, operation);
        return;
      }

      if (message?.type === "completed" && result.state.status !== "running") {
        ignoredApprovalIdsRef.current.clear();
        invalidateChapterQueries();
        invalidateNoteQueries();
        invalidateWorldEntryQueries();
        invalidateCharacterQueries();
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
      applyTranscriptEvent,
      invalidateChapterQueries,
      invalidateCharacterQueries,
      invalidateNoteQueries,
      invalidateWorldEntryQueries,
      onTaskTitleUpdated,
      onTokenUsage,
      onTaskUsageDelta,
      onTaskUsageSnapshot,
      projectId,
      queryClient,
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
            fallbackStage: getBestEffortContinueStage(
              transcriptStateRef.current.messages,
              agentKey,
            ),
            preservedStatus: transcriptStateRef.current.status,
          });
          commitTranscriptState(next);
          if (transportRetryAttemptRef.current === 1) {
            toast.error(i18n.t("assistant.agentConnectionFailed", { error: error.message }));
          }
        },
      );
    },
    [agentKey, commitTranscriptState, handleEvent],
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
      primaryAgentKey: agentKey,
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
        fallbackStage: getBestEffortContinueStage(transcriptStateRef.current.messages, agentKey),
        preservedStatus: loadedState.status,
      });
      commitTranscriptState(next);
      if (transportRetryAttemptRef.current === 1) {
        toast.error(i18n.t("assistant.agentConnectionFailed", { error: normalizedError.message }));
      }
    }
  }, [agentKey, attachAgentSocket, commitTranscriptState, sessionId]);

  const startSession = useCallback(
    async (
      userRequest: string,
      attachments?: Array<{ file?: File; uploadedAttachment?: AgentImageAttachment }>,
    ) => {
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
          currentStage: agentKey || AGENT_STAGE_TEXT.build,
        });

        const createResponse = await createAgentSession({
          project_id: projectId,
          model_id: modelId,
          ...(reasoningEffort ? { reasoning_effort: reasoningEffort } : {}),
          max_iterations: maxIterations,
          ...(agentKey ? { agent_key: agentKey } : {}),
        });

        if (projectIdRef.current !== projectId) return;
        onSessionCreated?.(createResponse);
        sessionIdRef.current = createResponse.session_id;
        activeModelIdRef.current = modelId;
        setSessionId(createResponse.session_id);
        queryClient.invalidateQueries({ queryKey: ["tasks", projectId], exact: false });
        attachAgentSocket(createResponse.session_id);
        await joinAgentSession(createResponse.session_id);
        if (projectIdRef.current !== projectId) return;
        const uploadedAttachments = attachments?.length
          ? await Promise.all(
              attachments.flatMap((attachment) =>
                attachment.file
                  ? [uploadAgentImageAttachment(createResponse.session_id, attachment.file)]
                  : [],
              ),
            )
          : undefined;
        await sendAgentMessage(
          createResponse.session_id,
          userRequest,
          undefined,
          undefined,
          undefined,
          uploadedAttachments,
        );
      } catch (error) {
        if (projectIdRef.current !== projectId) return;
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
      agentKey,
      attachAgentSocket,
      commitTranscriptState,
      maxIterations,
      modelId,
      onSessionCreated,
      projectId,
      queryClient,
      reasoningEffort,
      updateTranscriptState,
    ],
  );

  const sendMessage = useCallback(
    async (
      message: string,
      attachments?: Array<{ file?: File; uploadedAttachment?: AgentImageAttachment }>,
    ) => {
      const activeSessionId = sessionIdRef.current ?? sessionId;
      if (!activeSessionId) {
        toast.error(i18n.t("assistant.sessionNotFound"));
        return;
      }
      if (pendingMessageRef.current) {
        toast.error(i18n.t("writing.aiSidebar.cannotSendPendingMessage"));
        return;
      }

      const sessionWasRunning = transcriptStateRef.current.isRunning;
      const optimisticMessage = sessionWasRunning ? null : createOptimisticUserMessage(message);

      try {
        suppressSocketEventsAfterAbortRef.current = false;
        transportRetryAttemptRef.current = 0;
        updateTranscriptState((current) => ({
          ...current,
          messages: optimisticMessage
            ? [...current.messages.filter((item) => item.type !== "error"), optimisticMessage]
            : current.messages.filter((item) => item.type !== "error"),
          status: "running",
          isRunning: true,
          currentStage: getBestEffortContinueStage(current.messages, agentKey),
        }));

        if (!socketUnsubscribeRef.current) {
          attachAgentSocket(activeSessionId);
        }
        await joinAgentSession(activeSessionId);
        const uploadedAttachments = attachments?.length
          ? await Promise.all(
              attachments.flatMap((attachment) =>
                attachment.file
                  ? [uploadAgentImageAttachment(activeSessionId, attachment.file)]
                  : [],
              ),
            )
          : undefined;
        const existingAttachments = attachments?.flatMap((attachment) =>
          attachment.uploadedAttachment ? [attachment.uploadedAttachment] : [],
        );
        const messageAttachments = [...(existingAttachments ?? []), ...(uploadedAttachments ?? [])];
        const nextModelId = modelId === activeModelIdRef.current ? undefined : modelId;
        const response = await sendAgentMessage(
          activeSessionId,
          message,
          nextModelId,
          reasoningEffort,
          agentKey,
          messageAttachments.length > 0 ? messageAttachments : undefined,
        );
        if (response.model_updated && nextModelId) activeModelIdRef.current = nextModelId;
        if (response.queued && response.pending_message) {
          syncPendingMessageState(createPendingUserMessage(response.pending_message));
        }
      } catch (error) {
        console.error("Failed to send message:", error);
        updateTranscriptState((current) => ({
          ...current,
          messages: optimisticMessage
            ? current.messages.filter((item) => !(item.isDraft && item.content === message))
            : current.messages,
          status: "error",
          isRunning: false,
          currentStage: "",
        }));
        toast.error(i18n.t("assistant.sendMessageFailed"));
      }
    },
    [
      agentKey,
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
    async (actionId: string, answer: ClarificationAnswerItem[], skipped = false) => {
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
          currentStage: getBestEffortContinueStage(current.messages, agentKey),
        }));
        if (!socketUnsubscribeRef.current) {
          attachAgentSocket(sessionId);
          await joinAgentSession(sessionId);
        }
        await submitAgentQuestionAnswer(sessionId, actionId, answer, skipped);
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
    [agentKey, attachAgentSocket, sessionId, updateTranscriptState],
  );

  const handleBatchDecision = useCallback(
    async (
      panel: AgentMessage,
      decision: { approved?: boolean; answer?: ClarificationAnswerItem[]; skipped?: boolean },
    ) => {
      const batchId = panel.interruptBatchId;
      if (!batchId || panel.interruptBatchTotal === undefined) return;
      const current = interruptBatchRef.current;
      if (!current || current.batchId !== batchId) return;
      const interruptId = panel.correlationId || panel.id;
      current.decisions[interruptId] = {
        interrupt_id: interruptId,
        action_type: panel.type === "approval" ? "tool_approval" : "clarification",
        ...(panel.type === "approval"
          ? { approval_id: interruptId, approved: decision.approved }
          : { action_id: interruptId, answer: decision.answer, skipped: decision.skipped }),
      };
      const decisionCount = Object.keys(current.decisions).length;
      const batchTotal = panel.interruptBatchTotal ?? current.panels.length;
      updateTranscriptState((state) => ({
        ...state,
        messages: state.messages.map((item) =>
          item.id === panel.id ? { ...item, status: "completed" } : item,
        ),
        status: decisionCount < batchTotal ? state.status : "running",
        isRunning: decisionCount >= batchTotal,
      }));
      if (current.panels.length < batchTotal || decisionCount < batchTotal) return;
      try {
        await submitAgentInterruptBatch(
          sessionId || "",
          batchId,
          Object.values(current.decisions).map((item) => ({
            interrupt_id: String(item.interrupt_id),
            action_type: item.action_type as "tool_approval" | "clarification",
            approval_id: typeof item.approval_id === "string" ? item.approval_id : undefined,
            approved: typeof item.approved === "boolean" ? item.approved : undefined,
            action_id: typeof item.action_id === "string" ? item.action_id : undefined,
            answer: Array.isArray(item.answer) ? item.answer : undefined,
            skipped: item.skipped === true,
          })),
        );
        interruptBatchRef.current = null;
      } catch (error) {
        console.error("Interrupt batch resume failed:", error);
        updateTranscriptState((state) => ({
          ...state,
          messages: state.messages.map((item) =>
            item.interruptBatchId === batchId ? { ...item, status: "pending" } : item,
          ),
          status: current.panels.some((item) => item.type === "approval")
            ? "waiting_approval"
            : "waiting_answer",
          isRunning: false,
        }));
        toast.error(i18n.t("assistant.toolApprovalFailed"));
      }
    },
    [sessionId, updateTranscriptState],
  );

  const resetSession = useCallback(() => {
    sessionIdRef.current = null;
    activeModelIdRef.current = null;
    suppressSocketEventsAfterAbortRef.current = false;
    transportRetryAttemptRef.current = 0;
    suppressNextErrorAfterCompactionErrorRef.current = false;
    ignoredApprovalIdsRef.current.clear();
    interruptBatchRef.current = null;
    manualCompactionPreviousStateRef.current = null;
    syncPendingMessageState(null);
    syncCompactingState(false);
    setIsRollbacking(false);
    setSessionId(null);
    commitTranscriptState(createAgentTranscriptLiveState());
    socketUnsubscribeRef.current?.();
    socketUnsubscribeRef.current = null;
  }, [commitTranscriptState, syncCompactingState, syncPendingMessageState]);

  useEffect(() => {
    resetSession();
  }, [projectId, resetSession]);

  const abortSession = useCallback(async () => {
    const activeSessionId = sessionId;
    const previousTranscriptState = {
      ...transcriptStateRef.current,
      messages: [...transcriptStateRef.current.messages],
    };
    const previousInterruptBatch = interruptBatchRef.current;
    const previousPendingMessage = pendingMessageRef.current;
    const previousIsCompacting = isCompactingRef.current;
    const previousManualCompactionState = manualCompactionPreviousStateRef.current;
    suppressSocketEventsAfterAbortRef.current = true;
    transportRetryAttemptRef.current = 0;
    suppressNextErrorAfterCompactionErrorRef.current = false;
    interruptBatchRef.current = null;
    manualCompactionPreviousStateRef.current = null;
    socketUnsubscribeRef.current?.();
    socketUnsubscribeRef.current = null;
    syncPendingMessageState(null);
    syncCompactingState(false);
    updateTranscriptState((current) =>
      abortCompactionTranscriptState(
        {
          ...current,
          messages: clearPendingInterruptMessages(
            clearRetryMessages(cancelStreamingAgentMessages(current.messages)),
          ),
        },
        activeSessionId ?? undefined,
      ),
    );

    if (activeSessionId) {
      try {
        await cancelAgentSession(activeSessionId);
      } catch (error) {
        console.error("Failed to cancel agent session:", error);
        interruptBatchRef.current = previousInterruptBatch;
        manualCompactionPreviousStateRef.current = previousManualCompactionState;
        suppressSocketEventsAfterAbortRef.current = false;
        syncPendingMessageState(previousPendingMessage);
        syncCompactingState(previousIsCompacting);
        commitTranscriptState(previousTranscriptState);
        attachAgentSocket(activeSessionId);
        await joinAgentSession(activeSessionId).catch((joinError) => {
          console.error("Failed to restore agent session connection:", joinError);
        });
      }
    }
  }, [
    attachAgentSocket,
    commitTranscriptState,
    sessionId,
    syncCompactingState,
    syncPendingMessageState,
    updateTranscriptState,
  ]);

  const loadSession = useCallback(
    (
      existingSessionId: string,
      existingMessages: AgentMessage[],
      options: {
        reconnect?: boolean;
        isRemoteRunning?: boolean;
        primaryAgentKey?: string;
        pendingInterrupts?: Record<string, unknown>[];
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

      const pendingInterruptMessages = buildPendingInterruptMessages(
        options.pendingInterrupts ?? [],
      );
      const loadedMessages = [
        ...existingMessages,
        ...pendingInterruptMessages.filter(
          (interrupt) => !existingMessages.some((message) => message.id === interrupt.id),
        ),
      ];
      const pendingBatch = pendingInterruptMessages.find(
        (message) => message.interruptBatchId && message.interruptBatchTotal,
      );
      if (pendingBatch?.interruptBatchId && pendingBatch.interruptBatchTotal) {
        interruptBatchRef.current = {
          batchId: pendingBatch.interruptBatchId,
          panels: pendingInterruptMessages
            .filter((message) => message.interruptBatchId === pendingBatch.interruptBatchId)
            .sort(
              (left, right) => (left.interruptBatchIndex ?? 0) - (right.interruptBatchIndex ?? 0),
            ),
          decisions: {},
        };
      } else {
        interruptBatchRef.current = null;
      }
      const loadedState = getLoadedAgentSessionState({
        messages: loadedMessages,
        isRemoteRunning: options.isRemoteRunning,
        primaryAgentKey: options.primaryAgentKey ?? agentKey,
      });
      commitTranscriptState({
        messages: loadedMessages,
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
            fallbackStage: getBestEffortContinueStage(
              transcriptStateRef.current.messages,
              options.primaryAgentKey ?? agentKey,
            ),
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
    [
      agentKey,
      attachAgentSocket,
      commitTranscriptState,
      syncCompactingState,
      syncPendingMessageState,
    ],
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
    async (messageId: string): Promise<RollbackInputRestore | null> => {
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
          invalidateCharacterQueries();

          toast.success(i18n.t("assistant.rollbackSuccess"));

          return {
            content: result.restored_message_content,
            attachments: result.restored_attachments,
          };
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
      invalidateCharacterQueries,
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
        const result = await forkAgentSession(
          activeSessionId,
          sourceRevisionId,
          modelId,
          reasoningEffort,
        );
        queryClient.invalidateQueries({ queryKey: ["tasks", projectId], exact: false });
        toast.success(i18n.t("assistant.forkSuccess"));
        return result;
      } catch (error) {
        console.error("Fork failed:", error);
        toast.error(i18n.t("assistant.forkFailed"));
        return null;
      }
    },
    [isRollbacking, isRunning, modelId, projectId, queryClient, reasoningEffort, sessionId],
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
    handleBatchDecision,
    abortSession,
  };
}
