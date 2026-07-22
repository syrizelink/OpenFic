import type { AgentMessage } from "@/lib/agent.types";
import type { TaskListItem, TaskMessage } from "@/lib/task.types";

import { parseUtcTimestamp } from "./date-utils";
import { isRecord, normalizeToolResult } from "./tool-result-normalization";

function isPermissionRequiredToolResult(result: Record<string, unknown> | null): boolean {
  return result?.reason === "permission_required";
}

function isHiddenSystemReminderContent(content: string): boolean {
  return /^<system-reminder\b/i.test(content.trim());
}

const SUBAGENT_AGENT_IDS = new Set(["explore", "composer", "writer", "reviewer"]);
const SUBAGENT_ORCHESTRATION_TOOL_NAMES = new Set([
  "dispatch_subagent",
  "notify_subagent",
  "recycle_subagent",
]);

function getTaskMessageToolName(message: TaskMessage): string | undefined {
  const payloadToolName = message.payload?.tool_name;
  if (typeof payloadToolName === "string" && payloadToolName) return payloadToolName;
  const toolCallName = message.toolCalls?.find(
    (toolCall) => typeof toolCall.name === "string",
  )?.name;
  return typeof toolCallName === "string" ? toolCallName : undefined;
}

function isSubagentInternalTaskMessage(message: TaskMessage): boolean {
  if (message.agentId && SUBAGENT_AGENT_IDS.has(message.agentId)) return true;
  return false;
}

function getPayloadToolResult(
  payload: Record<string, unknown>,
  messageStatus: TaskMessage["messageStatus"],
): Record<string, unknown> | null {
  if (!("tool_result" in payload)) return null;
  return normalizeToolResult(payload.tool_result, {
    status: messageStatus,
    success: payload.success,
    toolCallId: payload.tool_call_id,
    toolName: payload.tool_name,
  });
}

function getToolIdentity(
  message: TaskMessage,
  messagePayload: Record<string, unknown>,
  toolResult: Record<string, unknown> | null,
): string | null {
  const payloadToolCallId = messagePayload.tool_call_id;
  if (typeof payloadToolCallId === "string" && payloadToolCallId)
    return `call:${payloadToolCallId}`;

  const resultToolCallId = toolResult?.tool_call_id;
  if (typeof resultToolCallId === "string" && resultToolCallId) return `call:${resultToolCallId}`;

  const payloadDispatchId = messagePayload.dispatch_id;
  if (typeof payloadDispatchId === "string" && payloadDispatchId)
    return `dispatch:${payloadDispatchId}`;

  const resultDispatchId = toolResult?.dispatch_id;
  if (typeof resultDispatchId === "string" && resultDispatchId)
    return `dispatch:${resultDispatchId}`;

  const payloadChildRunId = messagePayload.child_run_id;
  if (typeof payloadChildRunId === "string" && payloadChildRunId)
    return `child:${payloadChildRunId}`;

  const resultChildRunId = toolResult?.child_run_id;
  if (typeof resultChildRunId === "string" && resultChildRunId) return `child:${resultChildRunId}`;

  const resultMetadata = toolResult?.metadata;
  if (resultMetadata && typeof resultMetadata === "object" && !Array.isArray(resultMetadata)) {
    const metadataToolCallId = (resultMetadata as Record<string, unknown>).tool_call_id;
    if (typeof metadataToolCallId === "string" && metadataToolCallId)
      return `call:${metadataToolCallId}`;

    const metadataDispatchId = (resultMetadata as Record<string, unknown>).dispatch_id;
    if (typeof metadataDispatchId === "string" && metadataDispatchId)
      return `dispatch:${metadataDispatchId}`;

    const metadataChildRunId = (resultMetadata as Record<string, unknown>).child_run_id;
    if (typeof metadataChildRunId === "string" && metadataChildRunId)
      return `child:${metadataChildRunId}`;

    const metadataApprovalId = (resultMetadata as Record<string, unknown>).approval_id;
    if (typeof metadataApprovalId === "string" && metadataApprovalId)
      return `approval:${metadataApprovalId}`;
  }

  const payloadApprovalId = messagePayload.approval_id;
  if (typeof payloadApprovalId === "string" && payloadApprovalId)
    return `approval:${payloadApprovalId}`;

  if (message.correlationId) return `corr:${message.correlationId}`;
  if (message.id) return `msg:${message.id}`;

  return null;
}

function getTaskMessageRevisionId(
  payload: Record<string, unknown>,
  metadata?: Record<string, unknown> | null,
): string | undefined {
  const payloadRevisionId = payload.revision_id;
  if (typeof payloadRevisionId === "string" && payloadRevisionId) return payloadRevisionId;
  const metadataRevisionId = metadata?.revision_id;
  return typeof metadataRevisionId === "string" && metadataRevisionId
    ? metadataRevisionId
    : undefined;
}

function asAgentMessageStatus(value: unknown): AgentMessage["status"] | undefined {
  return value === "pending" || value === "running" || value === "completed" || value === "error"
    ? value
    : undefined;
}

function getToolMessageStatus(
  messageStatus: TaskMessage["messageStatus"],
  toolSuccess: boolean,
): AgentMessage["status"] {
  const normalizedStatus = asAgentMessageStatus(messageStatus) ?? "completed";
  if (!toolSuccess) return "error";
  return normalizedStatus;
}

function getToolSuccess(
  payload: Record<string, unknown>,
  toolResult: Record<string, unknown> | null,
  toolName: string | undefined,
  messageStatus: TaskMessage["messageStatus"],
): boolean {
  void toolName;
  if (typeof payload.success === "boolean") return payload.success;
  if (typeof toolResult?.success === "boolean") return toolResult.success;
  return asAgentMessageStatus(messageStatus) !== "error";
}

export function buildAgentMessagesFromTaskMessages(
  taskMessages: TaskMessage[],
  task: TaskListItem,
  taskCreatedAt: string,
): AgentMessage[] {
  const hasDispatchSubagent = taskMessages.some((message) => {
    const toolName = getTaskMessageToolName(message);
    return typeof toolName === "string" && SUBAGENT_ORCHESTRATION_TOOL_NAMES.has(toolName);
  });
  const pendingToolCalls = new Map<string, Record<string, unknown>>();
  const visibleToolIndexByKey = new Map<string, number>();
  const agentMessages: AgentMessage[] = [];
  const dedupedToolNames = new Set([
    "ask_user",
    "dispatch_subagent",
    "notify_subagent",
    "recycle_subagent",
  ]);

  const makeToolKey = (
    toolName: string | undefined,
    message: TaskMessage,
    messagePayload: Record<string, unknown>,
    toolResult: Record<string, unknown> | null,
  ) => {
    if (!toolName || !dedupedToolNames.has(toolName)) return null;
    const identity = getToolIdentity(message, messagePayload, toolResult);
    if (identity) return `${toolName}:${identity}`;
    if (toolName === "ask_user") {
      const questions = messagePayload.questions;
      return `${toolName}:${JSON.stringify(questions ?? [])}`;
    }
    return toolName;
  };

  taskMessages.forEach((msg, index) => {
    if (isHiddenSystemReminderContent(msg.content)) return;
    if (hasDispatchSubagent && isSubagentInternalTaskMessage(msg)) return;

    const content = msg.content;
    const structuredMessageType = msg.messageType ?? undefined;
    const payload = msg.payload ?? {};
    const revisionId = getTaskMessageRevisionId(payload, msg.metadata);
    const timestamp = parseUtcTimestamp(msg.createdAt || taskCreatedAt);
    const assistantTimestamp = parseUtcTimestamp(msg.updatedAt || msg.createdAt || taskCreatedAt);
    const isNodeBoundaryMessage =
      structuredMessageType === "node_start" || structuredMessageType === "node_end";

    if (msg.displayChannel === "hidden" && !isNodeBoundaryMessage) return;

    if (msg.role === "assistant" && msg.toolCalls?.length) {
      if (msg.content.trim()) {
        agentMessages.push({
          id: msg.id || `assistant-${task.id}-${index}`,
          type: "text",
          role: "assistant",
          status: (msg.messageStatus as AgentMessage["status"]) || "completed",
          display: "list",
          payload: msg.payload ?? { kind: "assistant_output" },
          correlationId: msg.correlationId,
          timestamp: assistantTimestamp,
          content: msg.content,
          agent: msg.agentId as AgentMessage["agent"],
        });
      }
      msg.toolCalls.forEach((toolCall) => {
        const id = toolCall.id;
        if (typeof id === "string") pendingToolCalls.set(id, toolCall);
      });
      return;
    }

    if (structuredMessageType) {
      if (structuredMessageType === "node_start" || structuredMessageType === "node_end") {
        agentMessages.push({
          id: msg.id || `node-${task.id}-${index}`,
          type: structuredMessageType,
          role: "system",
          status: (msg.messageStatus as AgentMessage["status"]) || "completed",
          display: msg.displayChannel === "hidden" ? "hidden" : "list",
          payload,
          correlationId: msg.correlationId,
          timestamp,
          content,
          agent: msg.agentId as AgentMessage["agent"],
        });
        return;
      }

      if (structuredMessageType === "user_request") {
        agentMessages.push({
          id: msg.id || `user-${task.id}-${index}`,
          type: "user_request",
          role: "user",
          status: (msg.messageStatus as AgentMessage["status"]) || "completed",
          display: "list",
          payload,
          correlationId: msg.correlationId,
          timestamp: msg.role === "assistant" ? assistantTimestamp : timestamp,
          content,
          revisionId,
          isCheckpoint: Boolean(revisionId),
        });
        return;
      }

      if (structuredMessageType === "text") {
        agentMessages.push({
          id: msg.id || `text-${task.id}-${index}`,
          type: "text",
          role: msg.role,
          status: (msg.messageStatus as AgentMessage["status"]) || "completed",
          display: "list",
          payload,
          correlationId: msg.correlationId,
          timestamp: msg.role === "assistant" ? assistantTimestamp : timestamp,
          content,
          revisionId,
          isCheckpoint: Boolean(revisionId),
        });
        return;
      }

      if (structuredMessageType === "reasoning" || structuredMessageType === "agent_thinking") {
        agentMessages.push({
          id: msg.id || `reasoning-${task.id}-${index}`,
          type: "reasoning",
          role: "assistant",
          status: (msg.messageStatus as AgentMessage["status"]) || "completed",
          display: "list",
          payload,
          correlationId: msg.correlationId,
          timestamp,
          content,
          agent: msg.agentId as AgentMessage["agent"],
          isStreaming: msg.messageStatus === "running",
          thinkingDurationMs:
            typeof payload.duration_ms === "number" ? payload.duration_ms : undefined,
        });
        return;
      }

      if (structuredMessageType === "compaction") {
        agentMessages.push({
          id: msg.id || `compaction-${task.id}-${index}`,
          type: "compaction",
          role: "system",
          status: (msg.messageStatus as AgentMessage["status"]) || "completed",
          display: "list",
          payload,
          correlationId: msg.correlationId,
          timestamp,
          content,
        });
        return;
      }

      if (structuredMessageType === "approval") {
        return;
      }

      if (structuredMessageType === "question") {
        return;
      }

      if (structuredMessageType === "tool") {
        const toolResult = getPayloadToolResult(payload, msg.messageStatus);
        if (isPermissionRequiredToolResult(toolResult)) return;
        const toolName = typeof payload.tool_name === "string" ? payload.tool_name : undefined;
        const toolArgs = isRecord(payload.tool_args) ? payload.tool_args : undefined;
        const toolSuccess = getToolSuccess(payload, toolResult, toolName, msg.messageStatus);
        const toolKey = makeToolKey(toolName, msg, payload, toolResult);
        const nextToolMessage: AgentMessage = {
          id: msg.id || `tool-${task.id}-${index}`,
          type: "tool",
          role: "tool",
          status: getToolMessageStatus(msg.messageStatus, toolSuccess),
          display: "list",
          payload,
          correlationId: msg.correlationId,
          timestamp,
          content,
          toolName,
          toolNames: toolName ? [toolName] : undefined,
          toolArgs,
          partialToolArgs:
            payload.partial_tool_args && typeof payload.partial_tool_args === "object"
              ? (payload.partial_tool_args as Record<string, unknown>)
              : undefined,
          toolResult: toolResult ?? undefined,
          toolSuccess,
          confirmedPlan: payload.confirmed_plan as AgentMessage["confirmedPlan"],
          outlineData: payload.outline_data as AgentMessage["outlineData"],
          reviewData: payload.review_data as AgentMessage["reviewData"],
          reviewPassed:
            typeof payload.review_passed === "boolean" ? payload.review_passed : undefined,
        };
        if (toolKey) {
          const previousIndex = visibleToolIndexByKey.get(toolKey);
          if (previousIndex !== undefined) {
            agentMessages[previousIndex] = nextToolMessage;
          } else {
            visibleToolIndexByKey.set(toolKey, agentMessages.length);
            agentMessages.push(nextToolMessage);
          }
          return;
        }
        agentMessages.push(nextToolMessage);
        return;
      }
    }

    if (msg.role === "tool") {
      if (msg.toolCallId) pendingToolCalls.delete(msg.toolCallId);
      return;
    }

    if (msg.role === "user") {
      agentMessages.push({
        id: msg.id || `user-${task.id}-${index}`,
        type: "user_request",
        role: "user",
        status: (msg.messageStatus as AgentMessage["status"]) || "completed",
        display: "list",
        payload,
        correlationId: msg.correlationId,
        timestamp,
        content,
        revisionId,
        isCheckpoint: Boolean(revisionId),
      });
      return;
    }

    if (msg.role === "assistant" && content.trim()) {
      agentMessages.push({
        id: msg.id || `assistant-${task.id}-${index}`,
        type: "agent_output",
        role: "assistant",
        status: (msg.messageStatus as AgentMessage["status"]) || "completed",
        display: "list",
        payload,
        correlationId: msg.correlationId,
        timestamp: assistantTimestamp,
        content,
        agent: msg.agentId as AgentMessage["agent"],
      });
    }
  });

  return agentMessages;
}
