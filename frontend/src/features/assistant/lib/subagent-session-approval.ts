import type { AgentEvent, AgentMessage, ToolApprovalData } from "@/lib/agent.types";

import { getString, isRecord } from "./tool-result-normalization";

interface PendingApprovalDetails {
  approvalId: string;
  payload: ToolApprovalData;
}

function getPendingApprovalDetails(pendingApproval: unknown): PendingApprovalDetails | null {
  const data = isRecord(pendingApproval) ? pendingApproval : null;
  if (!data || getString(data.type) !== "tool_approval") return null;

  const approvalId = getString(data.approval_id) || getString(data.id);
  if (!approvalId) return null;

  const toolArgs = isRecord(data.args) ? data.args : isRecord(data.tool_args) ? data.tool_args : {};
  const toolName = getString(data.tool_name) || "";
  const toolCallId = getString(data.tool_call_id);
  const toolResultPreview = isRecord(data.tool_result_preview)
    ? data.tool_result_preview
    : undefined;

  return {
    approvalId,
    payload: {
      approval_id: approvalId,
      tool_name: toolName,
      tool_call_id: toolCallId,
      tool_args: toolArgs,
      tool_result_preview: toolResultPreview,
      message: getString(data.message) || `是否允许调用 ${toolName}？`,
      interrupt_behavior: data.interrupt_behavior === "cancel" ? "cancel" : "block",
    },
  };
}

export function createPendingApprovalEvent(
  pendingApproval: unknown,
  createdAt?: string,
): AgentEvent | null {
  const details = getPendingApprovalDetails(pendingApproval);
  if (!details) return null;

  return {
    id: details.approvalId,
    correlation_id: details.approvalId,
    type: "approval",
    role: "system",
    status: "pending",
    display: "panel",
    created_at: createdAt,
    payload: details.payload as unknown as Record<string, unknown>,
  };
}

export function createPendingApprovalMessage(
  pendingApproval: unknown,
  createdAt?: string,
): AgentMessage | null {
  const details = getPendingApprovalDetails(pendingApproval);
  if (!details) return null;

  const timestamp = createdAt ? Date.parse(createdAt) || Date.now() : Date.now();
  return {
    id: details.approvalId,
    correlationId: details.approvalId,
    type: "approval",
    role: "system",
    status: "pending",
    display: "panel",
    timestamp,
    payload: details.payload as unknown as Record<string, unknown>,
    toolApproval: details.payload,
    content: details.payload.message,
  };
}
