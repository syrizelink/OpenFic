import type { AgentEvent, AgentMessage, AgentSessionStatus } from "@/lib/agent.types";
import i18n from "@/i18n";

import { mergeStreamingMessage } from "./streaming-message-merge";
import {
  clearRetryMessages,
  upsertRetryMessage,
} from "./retry-message-state";
import {
  stopStreamingReasoning,
  stopStreamingReasoningForAgentEvent,
  stopStreamingToolMessages,
} from "../hooks/use-agent-session-message-state";
import { parseUtcTimestamp } from "./date-utils";

export interface AgentTranscriptState {
  messages: AgentMessage[];
  status: AgentSessionStatus;
  isRunning: boolean;
  currentStage: string;
}

export interface AgentTranscriptEventOptions {
  defaultRunningStage?: string;
  approvalPreviewFactory?: (message: AgentMessage) => AgentMessage | null;
  getStageTextForAgent?: (agent?: string) => string | null;
  getStageTextForStage?: (stage?: string) => string | null;
  keepRunningOnCompleted?: (messages: AgentMessage[]) => boolean;
  fallbackAgent?: string;
}

export interface AgentTranscriptEventResult {
  message: AgentMessage | null;
  state: AgentTranscriptState;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isHiddenSystemReminderContent(content: string | undefined): boolean {
  return typeof content === "string" && /^<system-reminder\b/i.test(content.trim());
}

function normalizeClarificationQuestions(value: unknown): AgentMessage["questions"] {
  if (!Array.isArray(value)) return [];
  return value.reduce<NonNullable<AgentMessage["questions"]>>((result, item) => {
    if (typeof item === "string") {
      result.push({ title: item, options: [] });
      return result;
    }
    if (!isRecord(item) || typeof item.title !== "string" || !item.title.trim()) return result;
    const options = Array.isArray(item.options)
      ? item.options.reduce<NonNullable<NonNullable<AgentMessage["questions"]>[number]["options"]>>((optionResult, option) => {
          if (!isRecord(option) || typeof option.label !== "string" || !option.label.trim()) {
            return optionResult;
          }
          optionResult.push({
            label: option.label.trim(),
            description:
              typeof option.description === "string" ? option.description.trim() : undefined,
          });
          return optionResult;
        }, [])
      : [];
    result.push({
      title: item.title.trim(),
      description: typeof item.description === "string" ? item.description.trim() : undefined,
      options,
    });
    return result;
  }, []);
}

function getEventPayload(event: AgentEvent): Record<string, unknown> {
  return event.payload ?? {};
}

export function getStageTextForAgentKey(agent?: string): string | null {
  if (agent === "primary") return i18n.t("assistant.agentStatus.primary");
  if (agent === "explorer") return i18n.t("assistant.agentStatus.explorer");
  if (agent === "composer") return i18n.t("assistant.agentStatus.composer");
  if (agent === "writer") return i18n.t("assistant.agentStatus.writer");
  if (agent === "reviewer") return i18n.t("assistant.agentStatus.reviewer");
  return null;
}

export function getStageTextForStageKey(stage?: string): string | null {
  return getStageTextForAgentKey(stage);
}

function getMessageToolCallId(message: AgentMessage): string | null {
  const payloadToolCallId = message.payload?.tool_call_id;
  if (typeof payloadToolCallId === "string" && payloadToolCallId) return payloadToolCallId;
  const resultToolCallId = message.toolResult?.tool_call_id;
  if (typeof resultToolCallId === "string" && resultToolCallId) return resultToolCallId;
  return null;
}

function isPendingApprovalToolMessage(
  message: AgentMessage,
  approvalMessage: AgentMessage
): boolean {
  if (message.type !== "tool" || approvalMessage.type !== "approval") return false;
  if (!(message.isStreaming || message.status === "running")) return false;

  const approvalToolCallId = typeof approvalMessage.toolApproval?.tool_call_id === "string"
    ? approvalMessage.toolApproval.tool_call_id
    : undefined;
  if (approvalToolCallId) {
    return getMessageToolCallId(message) === approvalToolCallId;
  }

  const approvalToolName = approvalMessage.toolApproval?.tool_name;
  return Boolean(approvalToolName && message.toolName === approvalToolName);
}

function isSameToolMessageByFallback(item: AgentMessage, message: AgentMessage): boolean {
  if (item.type !== "tool" || message.type !== "tool") return false;
  if (!item.isStreaming && item.status !== "running") return false;
  if (!message.toolName || item.toolName !== message.toolName) return false;
  if (!item.agent || !message.agent || item.agent !== message.agent) return false;
  return true;
}

function isSameOptimisticUserMessage(item: AgentMessage, message: AgentMessage): boolean {
  if (!item.isDraft) return false;
  if (item.type !== "user_request" && !(item.type === "text" && item.role === "user")) return false;
  if (message.type !== "text" || message.role !== "user") return false;
  if (message.payload?.kind !== "user_request") return false;
  return item.content === message.content;
}

function getPayloadString(message: AgentMessage, key: string): string | null {
  const value = message.payload?.[key];
  return typeof value === "string" && value ? value : null;
}

function getPayloadNumber(message: AgentMessage, key: string): number | null {
  const value = message.payload?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isRunningCompactionMessageForSession(message: AgentMessage, sessionId?: string): boolean {
  if (message.type !== "compaction" || message.status !== "running") return false;
  if (!sessionId) return true;
  const payloadSessionId = getPayloadString(message, "session_id");
  return !payloadSessionId || payloadSessionId === sessionId;
}

export function removeRunningCompactionMessages(
  messages: AgentMessage[],
  sessionId?: string
): AgentMessage[] {
  let changed = false;
  const nextMessages = messages.filter((message) => {
    const shouldRemove = isRunningCompactionMessageForSession(message, sessionId);
    if (shouldRemove) changed = true;
    return !shouldRemove;
  });
  return changed ? nextMessages : messages;
}

export function failCompactionTranscriptState(
  state: AgentTranscriptState,
  sessionId?: string
): AgentTranscriptState {
  return {
    ...state,
    messages: removeRunningCompactionMessages(state.messages, sessionId),
    status: "error",
    isRunning: false,
    currentStage: "",
  };
}

export function restoreManualCompactionTranscriptState(
  state: AgentTranscriptState,
  previousState: Pick<AgentTranscriptState, "status" | "isRunning" | "currentStage"> | null,
  sessionId?: string
): AgentTranscriptState {
  return {
    ...state,
    messages: removeRunningCompactionMessages(state.messages, sessionId),
    status: previousState?.status ?? state.status,
    isRunning: previousState?.isRunning ?? state.isRunning,
    currentStage: previousState?.currentStage ?? state.currentStage,
  };
}

export function abortCompactionTranscriptState(
  state: AgentTranscriptState,
  sessionId?: string
): AgentTranscriptState {
  return {
    ...state,
    messages: removeRunningCompactionMessages(state.messages, sessionId),
    status: "idle",
    isRunning: false,
    currentStage: "",
  };
}

function isSameCompactionMessage(item: AgentMessage, message: AgentMessage): boolean {
  if (item.type !== "compaction" || message.type !== "compaction") return false;
  if (item.id === message.id) return true;

  const itemCompactionId = getPayloadString(item, "compaction_id");
  const messageCompactionId = getPayloadString(message, "compaction_id");
  if (itemCompactionId && itemCompactionId === messageCompactionId) return true;

  const itemSessionId = getPayloadString(item, "session_id");
  const messageSessionId = getPayloadString(message, "session_id");
  const sameSession = Boolean(itemSessionId && itemSessionId === messageSessionId);
  if (!sameSession) return false;

  const itemStartSeq = getPayloadNumber(item, "start_seq");
  const itemEndSeq = getPayloadNumber(item, "end_seq");
  const messageStartSeq = getPayloadNumber(message, "start_seq");
  const messageEndSeq = getPayloadNumber(message, "end_seq");
  if (
    itemStartSeq !== null
    && itemEndSeq !== null
    && messageStartSeq !== null
    && messageEndSeq !== null
    && itemStartSeq === messageStartSeq
    && itemEndSeq === messageEndSeq
  ) {
    return true;
  }

  return item.status === "running" && !itemCompactionId;
}

function isSameStreamMessage(item: AgentMessage, message: AgentMessage): boolean {
  if (item.id === message.id) return true;
  if (isSameCompactionMessage(item, message)) return true;
  if (message.correlationId && item.correlationId === message.correlationId) return true;
  if (isSameOptimisticUserMessage(item, message)) return true;
  if (item.type !== "tool" || message.type !== "tool") return false;
  const itemToolCallId = getMessageToolCallId(item);
  const messageToolCallId = getMessageToolCallId(message);
  return Boolean(itemToolCallId && itemToolCallId === messageToolCallId) || isSameToolMessageByFallback(item, message);
}

export function upsertTranscriptMessage(messages: AgentMessage[], message: AgentMessage): AgentMessage[] {
  const index = messages.findIndex((item) => isSameStreamMessage(item, message));
  if (index < 0) return [...messages, message];
  const next = [...messages];
  next[index] = {
    ...next[index],
    ...message,
    id: next[index].id,
  };
  return next;
}

export function upsertTranscriptStreamingMessage(messages: AgentMessage[], message: AgentMessage): AgentMessage[] {
  if (message.payload?.is_delta && ["text", "reasoning"].includes(message.type) && !message.content) return messages;
  if (message.payload?.is_delta && message.type === "tool" && !message.toolArgsText) {
    const index = messages.findIndex((item) => isSameStreamMessage(item, message));
    return index < 0 ? [...messages, message] : messages;
  }

  const index = messages.findIndex((item) => isSameStreamMessage(item, message));
  if (index < 0) return [...messages, message];

  const previous = messages[index];
  const mergedMessage = mergeStreamingMessage(previous, message);
  if (
    previous.content === mergedMessage.content
    && previous.status === mergedMessage.status
    && previous.toolArgsText === mergedMessage.toolArgsText
    && previous.partialToolArgs === mergedMessage.partialToolArgs
    && previous.toolResult === mergedMessage.toolResult
    && previous.thinkingDurationMs === mergedMessage.thinkingDurationMs
  ) return messages;
  const next = [...messages];
  next[index] = mergedMessage;
  return next;
}

export function stopTranscriptStreamingMessages(messages: AgentMessage[]): AgentMessage[] {
  return stopStreamingToolMessages(stopStreamingReasoning(messages));
}

function completeLatestAssistantMessage(
  messages: AgentMessage[],
  completedAt?: number
): AgentMessage[] {
  const lastAssistantIndex = messages.findLastIndex((message) => (
    (message?.type === "text" && message.role === "assistant")
    || message?.type === "agent_output"
  ));
  if (lastAssistantIndex < 0) return messages;

  let nextMessages = messages;
  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index];
    const isAssistantOutput =
      (message?.type === "text" && message.role === "assistant")
      || message?.type === "agent_output";
    if (!isAssistantOutput) continue;

    const isLastAssistantOutput = index === lastAssistantIndex;
    const timestamp = isLastAssistantOutput && typeof completedAt === "number"
      ? completedAt
      : message.timestamp;
    const shouldUpdate =
      message.status === "running"
      || message.isStreaming
      || (isLastAssistantOutput && message.timestamp !== timestamp);
    if (!shouldUpdate) continue;

    if (nextMessages === messages) {
      nextMessages = [...messages];
    }
    nextMessages[index] = {
      ...message,
      status: "completed",
      isStreaming: false,
      ...(isLastAssistantOutput ? { timestamp } : {}),
    };
  }
  return nextMessages;
}

function finalizeCompletedTranscriptMessages(
  messages: AgentMessage[],
  completedAt?: number
): AgentMessage[] {
  return completeLatestAssistantMessage(
    stopTranscriptStreamingMessages(messages),
    completedAt
  );
}

function normalizeTranscriptEvent(event: AgentEvent): AgentMessage | null {
  if (isHiddenSystemReminderContent(event.content)) return null;

  const payload = getEventPayload(event);
  const timestamp = parseUtcTimestamp(event.created_at);
  const base: AgentMessage = {
    id: event.correlation_id || event.id || event.message_id || `${event.type}-${timestamp}`,
    type: event.type as AgentMessage["type"],
    role: event.role,
    status: event.status,
    display: event.display,
    payload,
    correlationId: event.correlation_id,
    timestamp,
    content: event.content,
    agent: (event.agent as AgentMessage["agent"]) || undefined,
    revisionId: event.revision_id,
    isCheckpoint: event.is_checkpoint ?? event.isCheckpoint,
  };

  if (event.type === "text") return base;
  if (event.type === "retry") {
    return {
      ...base,
      type: "retry",
      content: event.content || (typeof payload.error_message === "string" ? payload.error_message : i18n.t("assistant.upstreamFailure")),
    };
  }
  if (event.type === "compaction") {
    return {
      ...base,
      type: "compaction",
      content: event.content || (event.status === "running" ? i18n.t("assistant.compactionRunning") : i18n.t("assistant.compactionDone")),
    };
  }
  if (event.type === "reasoning") {
    return {
      ...base,
      isStreaming: event.status === "running" || Boolean(payload.is_delta),
      thinkingDurationMs: typeof payload.duration_ms === "number" ? payload.duration_ms : undefined,
    };
  }
  if (event.type === "approval") {
    const toolResultPreview =
      payload.tool_result_preview && typeof payload.tool_result_preview === "object"
        ? payload.tool_result_preview as Record<string, unknown>
        : undefined;
    return {
      ...base,
      type: "approval",
      toolApproval: {
        approval_id: typeof payload.approval_id === "string" ? payload.approval_id : "",
        tool_name: typeof payload.tool_name === "string" ? payload.tool_name : "",
        tool_call_id: typeof payload.tool_call_id === "string" ? payload.tool_call_id : undefined,
        tool_args: payload.tool_args && typeof payload.tool_args === "object" ? payload.tool_args as Record<string, unknown> : {},
        tool_result_preview: toolResultPreview,
        message: typeof payload.message === "string" ? payload.message : event.content || i18n.t("assistant.toolApprovalRequiredFallback"),
        interrupt_behavior: payload.interrupt_behavior === "block" ? "block" : "cancel",
      },
    };
  }
  if (event.type === "question") {
    return {
      ...base,
      type: "question",
      questions: normalizeClarificationQuestions(payload.questions),
    };
  }
  if (event.type === "tool") {
    const toolName = typeof payload.tool_name === "string" ? payload.tool_name : undefined;
    const toolArgs = isRecord(payload.tool_args) ? payload.tool_args : undefined;
    return {
      ...base,
      type: "tool",
      toolName,
      toolNames: toolName ? [toolName] : undefined,
      toolArgs,
      toolArgsText: typeof payload.tool_args_text === "string" ? payload.tool_args_text : undefined,
      partialToolArgs:
        payload.partial_tool_args && typeof payload.partial_tool_args === "object"
          ? payload.partial_tool_args as Record<string, unknown>
          : undefined,
      toolResult: payload.tool_result && typeof payload.tool_result === "object"
        ? payload.tool_result as Record<string, unknown>
        : undefined,
      toolSuccess: typeof payload.success === "boolean" ? payload.success : event.status !== "error",
      confirmedPlan: payload.confirmed_plan as AgentMessage["confirmedPlan"],
      outlineData: payload.outline_data as AgentMessage["outlineData"],
      reviewData: payload.review_data as AgentMessage["reviewData"],
      reviewPassed: typeof payload.review_passed === "boolean" ? payload.review_passed : undefined,
      content: event.content || (typeof payload.outline === "string" ? payload.outline : undefined),
      isStreaming: event.status === "running" || Boolean(payload.is_delta),
    };
  }
  if (event.type === "task_completed") {
    return {
      ...base,
      type: "completed",
      finalContent: typeof payload.final_content === "string" ? payload.final_content : event.final_content,
      wordCount: typeof payload.word_count === "number" ? payload.word_count : event.word_count,
      iteration: typeof payload.iteration === "number" ? payload.iteration : event.iteration,
    };
  }
  if (event.type === "error") {
    return {
      ...base,
      type: "error",
      content: event.content || (payload.error as string) || i18n.t("assistant.agentRunFailed"),
    };
  }
  if (event.display === "hidden") return base;
  return null;
}

export function applyAgentTranscriptEvent(
  state: AgentTranscriptState,
  event: AgentEvent,
  options: AgentTranscriptEventOptions = {}
): AgentTranscriptEventResult {
  const message = normalizeTranscriptEvent(event);
  if (!message) {
    return { state, message: null };
  }

  const agentStage = options.getStageTextForAgent?.(event.agent) ?? options.getStageTextForAgent?.(options.fallbackAgent);
  const stageText = options.getStageTextForStage?.(event.stage) ?? agentStage ?? options.defaultRunningStage ?? "";

  if (["text", "retry", "compaction", "reasoning", "tool", "approval", "question", "error", "task_completed"].includes(event.type)) {
    const baseMessages = state.messages;

    if (message.type === "text" && message.role === "user") {
      if (message.payload?.kind === "question_answer") {
        return { state, message };
      }
      const finalizedMessages = finalizeCompletedTranscriptMessages(
        clearRetryMessages(baseMessages)
      );
      return {
        state: {
          ...state,
          messages: upsertTranscriptMessage(finalizedMessages, message),
        },
        message,
      };
    }

    if (message.type === "text" && message.role === "assistant") {
      const isRunning = message.status === "running" || message.isStreaming;
      return {
        state: {
          ...state,
          messages: upsertTranscriptStreamingMessage(
            clearRetryMessages(stopStreamingReasoning(baseMessages)),
            message
          ),
          status: isRunning ? "running" : state.status,
          isRunning: isRunning ? true : state.isRunning,
          currentStage: isRunning ? (state.currentStage || stageText) : state.currentStage,
        },
        message,
      };
    }

    if (message.type === "retry") {
      return {
        state: {
          ...state,
          messages: upsertRetryMessage(baseMessages.filter((item) => item.type !== "error"), message),
          status: "running",
          isRunning: true,
          currentStage: stageText || state.currentStage,
        },
        message,
      };
    }

    if (message.type === "compaction") {
      const isRunning = message.status === "running";
      const isManual = message.payload?.trigger === "manual";
      return {
        state: {
          ...state,
          messages: upsertTranscriptMessage(
            stopTranscriptStreamingMessages(clearRetryMessages(baseMessages)),
            message
          ),
          status: isRunning ? "running" : isManual ? "completed" : state.status,
          isRunning: isRunning ? true : isManual ? false : state.isRunning,
          currentStage: isRunning ? i18n.t("assistant.compactionRunning") : isManual ? "" : state.currentStage,
        },
        message,
      };
    }

    if (message.type === "reasoning") {
      const isRunning = message.status === "running" || message.isStreaming;
      return {
        state: {
          ...state,
          messages: upsertTranscriptStreamingMessage(clearRetryMessages(baseMessages), message),
          status: isRunning ? "running" : state.status,
          isRunning: isRunning ? true : state.isRunning,
          currentStage: isRunning ? (state.currentStage || stageText) : state.currentStage,
        },
        message,
      };
    }

    if (message.type === "completed") {
      const shouldKeepRunning = options.keepRunningOnCompleted?.(baseMessages) ?? false;
      return {
        state: {
          ...state,
          messages: finalizeCompletedTranscriptMessages(
            clearRetryMessages(baseMessages),
            message.timestamp
          ),
          status: shouldKeepRunning ? "running" : "completed",
          isRunning: shouldKeepRunning,
          currentStage: shouldKeepRunning ? (options.defaultRunningStage ?? stageText) : "",
        },
        message,
      };
    }

    if (message.type === "approval") {
      const previewToolMessage = options.approvalPreviewFactory?.(message) ?? null;
      const stopped = stopTranscriptStreamingMessages(clearRetryMessages(baseMessages))
        .filter((item) => item.type !== "approval" && item.type !== "tool_approval");
      const withoutPendingTool = previewToolMessage
        ? stopped
        : stopped.filter((item) => !isPendingApprovalToolMessage(item, message));
      const withPreview = previewToolMessage
        ? upsertTranscriptStreamingMessage(withoutPendingTool, previewToolMessage)
        : withoutPendingTool;
      const nextMessages = upsertTranscriptMessage(withPreview, message);
      return {
        state: {
          ...state,
          messages: nextMessages,
          status: "waiting_approval",
          isRunning: false,
          currentStage: "",
        },
        message,
      };
    }

    if (message.type === "question") {
      return {
        state: {
          ...state,
          messages: upsertTranscriptMessage(
            clearRetryMessages(stopStreamingReasoning(baseMessages)).filter((item) => item.type !== "question" && item.type !== "clarification"),
            message
          ),
          status: "waiting_answer",
          isRunning: false,
          currentStage: "",
        },
        message,
      };
    }

    if (message.type === "tool") {
      const nextMessages = upsertTranscriptStreamingMessage(
        clearRetryMessages(stopStreamingReasoning(baseMessages)).filter((item) => item.type !== "approval" && item.type !== "tool_approval"),
        message
      );
      return {
        state: {
          ...state,
          messages: nextMessages,
          status: message.status === "error" ? "running" : (message.status === "running" || message.isStreaming ? "running" : state.status),
          isRunning: message.status === "running" || message.isStreaming ? true : state.isRunning,
          currentStage: stageText || state.currentStage,
        },
        message,
      };
    }

    if (message.type === "error") {
      return {
        state: {
          ...state,
          messages: upsertTranscriptMessage(stopTranscriptStreamingMessages(clearRetryMessages(baseMessages)), message),
          status: "error",
          isRunning: false,
          currentStage: "",
        },
        message,
      };
    }
  }

  if (event.display === "hidden") {
    const applyHiddenEventToMessages = (nextMessage?: AgentMessage | null) => {
      const base = ["token_usage", "node_start", "node_end", "stage_start", "stage_transfer", "iteration_start", "task_completed"].includes(event.type)
        ? clearRetryMessages(state.messages)
        : state.messages;
      const next = stopStreamingReasoningForAgentEvent(base, event, nextMessage ?? undefined);
      return nextMessage ? upsertTranscriptMessage(next, nextMessage) : next;
    };

    if (event.type === "task_title_updated") {
      return {
        state: {
          ...state,
          messages: applyHiddenEventToMessages(),
        },
        message: null,
      };
    }

    if (event.type === "token_usage") {
      return {
        state: {
          ...state,
          messages: applyHiddenEventToMessages(),
        },
        message: null,
      };
    }

    if (event.type === "node_start" || event.type === "node_end") {
      const activeNode =
        typeof event.payload?.current_node === "string"
          ? event.payload.current_node
          : event.type === "node_start" && typeof event.payload?.node === "string"
            ? event.payload.node
            : typeof event.agent === "string"
              ? event.agent
              : undefined;
      const nextStage = options.getStageTextForStage?.(activeNode) ?? options.getStageTextForAgent?.(event.agent) ?? stageText;
      return {
        state: {
          ...state,
          messages: applyHiddenEventToMessages(normalizeTranscriptEvent(event)),
          status: "running",
          isRunning: true,
          currentStage: event.type === "node_end" && !nextStage ? "" : nextStage,
        },
        message: normalizeTranscriptEvent(event),
      };
    }

    if (event.type === "stage_start" || event.type === "stage_transfer") {
      const nextStage =
        options.getStageTextForStage?.(event.payload?.stage as string)
        ?? options.getStageTextForAgent?.(event.agent)
        ?? stageText;
      return {
        state: {
          ...state,
          messages: applyHiddenEventToMessages(),
          status: "running",
          isRunning: true,
          currentStage: nextStage,
        },
        message: null,
      };
    }

    if (event.type === "iteration_start") {
      return {
        state: {
          ...state,
          messages: applyHiddenEventToMessages(),
          status: "running",
          isRunning: true,
          currentStage: options.defaultRunningStage ?? stageText,
        },
        message: null,
      };
    }

    if (event.type === "task_completed") {
      const base = applyHiddenEventToMessages();
      const shouldKeepRunning = options.keepRunningOnCompleted?.(state.messages) ?? false;
      return {
        state: {
          ...state,
          messages: stopTranscriptStreamingMessages(base),
          status: shouldKeepRunning ? "running" : "completed",
          isRunning: shouldKeepRunning,
          currentStage: shouldKeepRunning ? (options.defaultRunningStage ?? stageText) : "",
        },
        message: null,
      };
    }
  }

  return { state, message };
}
