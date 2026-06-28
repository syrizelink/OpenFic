import type { AgentEvent } from "@/lib/agent.types";

import { getString, isRecord, normalizeToolResult } from "./tool-result-normalization";

export const AGENT_SOCKET_EVENTS = [
  "agent:text",
  "agent:pending_message",
  "agent:token",
  "agent:reasoning",
  "agent:tool_call",
  "agent:tool_result",
  "agent:node",
  "agent:retry",
  "agent:interrupt",
  "agent:usage",
  "agent:task_usage_snapshot",
  "agent:task_usage_delta",
  "agent:task_title_updated",
  "agent:chapter_refresh",
  "agent:note_refresh",
  "agent:compaction_start",
  "agent:compaction_success",
  "agent:compaction_error",
  "agent:done",
  "agent:error",
] as const;

export type AgentSocketEventName = (typeof AGENT_SOCKET_EVENTS)[number];

function getContent(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function isHiddenSystemReminderContent(content: string): boolean {
  return /^<system-reminder\b/i.test(content.trim());
}

function eventId(prefix: string, data: Record<string, unknown>): string {
  return getString(data.tool_call_id)
    || getString(data.dispatch_id)
    || getString(data.run_id)
    || getString(data.id)
    || `${prefix}-${Date.now()}`;
}

function matchesSession(sessionId: string, data: Record<string, unknown>): boolean {
  const payload = isRecord(data.payload) ? data.payload : null;
  const eventSessionId = getString(data.session_id) || (payload ? getString(payload.session_id) : undefined);
  return !eventSessionId || eventSessionId === sessionId;
}

function getToolEventStatus(_toolName: string, result: Record<string, unknown>): AgentEvent["status"] {
  return result.success === false ? "error" : "completed";
}

function getToolEventSuccess(_toolName: string, result: Record<string, unknown>): boolean {
  return result.success !== false;
}

export function toAgentEvent(
  eventName: AgentSocketEventName,
  sessionId: string,
  rawData: unknown
): AgentEvent | null {
  const data = isRecord(rawData) ? rawData : {};
  if (!matchesSession(sessionId, data)) return null;

  if (eventName === "agent:text") {
    const content = getContent(data.content);
    if (isHiddenSystemReminderContent(content)) return null;
    return {
      ...data,
      type: getString(data.type) || "text",
      role: data.role === "user" ? "user" : "assistant",
      status: data.status === "running" ? "running" : "completed",
      display: data.display === "hidden" ? "hidden" : "list",
      content,
      payload: isRecord(data.payload) ? data.payload : {},
    } as AgentEvent;
  }

  if (eventName === "agent:pending_message") {
    const messageId = getString(data.message_id);
    const action = getString(data.action);
    if (!messageId || !action) return null;
    return {
      id: `pending:${messageId}:${action}`,
      correlation_id: `pending:${messageId}`,
      type: "pending_message",
      role: "system",
      status: action === "queued" ? "pending" : "completed",
      display: "hidden",
      content: getContent(data.content),
      payload: {
        action,
        message_id: messageId,
        content: getContent(data.content),
        created_at: getString(data.created_at),
      },
    };
  }

  if (eventName === "agent:token") {
    const id = eventId("agent-token", data);
    return {
      id,
      correlation_id: id,
      type: "text",
      role: "assistant",
      status: "running",
      display: "list",
      content: getContent(data.content),
      payload: { is_delta: true },
    };
  }

  if (eventName === "agent:reasoning") {
    const id = `${eventId("agent-reasoning", data)}:reasoning`;
    return {
      id,
      correlation_id: id,
      type: "reasoning",
      role: "assistant",
      status: "running",
      display: "list",
      content: getContent(data.content),
      payload: { is_delta: true },
    };
  }

  if (eventName === "agent:tool_call") {
    const id = eventId("agent-tool", data);
    const input = data.input;
    const partialArgsText = getString(data.partial_args);
    const argsText = getString(data.args_text);
    return {
      id,
      correlation_id: id,
      type: "tool",
      role: "tool",
      status: "running",
      display: "list",
      payload: {
        tool_call_id: getString(data.tool_call_id),
        tool_name: getString(data.tool) || getString(data.tool_name) || "",
        tool_args: isRecord(input) ? input : undefined,
        partial_tool_args_text: partialArgsText,
        tool_args_text: argsText || (typeof input === "string" ? input : JSON.stringify(input ?? {})),
        is_delta: data.is_delta === true,
      },
    };
  }

  if (eventName === "agent:tool_result") {
    const id = eventId("agent-tool", data);
    const result = normalizeToolResult(data.output);
    const input = data.input;
    const toolName = getString(data.tool) || getString(data.tool_name) || getString(result.tool_name) || "";
    const toolSuccess = getToolEventSuccess(toolName, result);
    return {
      id,
      correlation_id: id,
      type: "tool",
      role: "tool",
      status: getToolEventStatus(toolName, result),
      display: "list",
      payload: {
        tool_call_id: getString(data.tool_call_id) || getString(result.tool_call_id),
        tool_name: toolName,
        tool_args: isRecord(input) ? input : undefined,
        tool_args_text: typeof input === "string" ? input : JSON.stringify(input ?? {}),
        tool_result: result,
        success: toolSuccess,
      },
    };
  }

  if (eventName === "agent:node") {
    const id = `${eventId("agent-node", data)}:${getString(data.phase) === "end" ? "end" : "start"}`;
    const node = getString(data.node);
    const phase = getString(data.phase) === "end" ? "end" : "start";
    const currentNode = getString(data.current_node);
    const previousNode = getString(data.previous_node);
    const status =
      getString(data.status) === "error" ? "error" : phase === "end" ? "completed" : "running";
    return {
      id,
      correlation_id: id,
      type: phase === "end" ? "node_end" : "node_start",
      role: "system",
      status,
      display: "hidden",
      agent: node,
      payload: {
        node,
        phase,
        status,
        current_node: currentNode,
        previous_node: previousNode,
      },
    };
  }

  if (eventName === "agent:retry") {
    const node = getString(data.node);
    const attempt = Number(data.attempt ?? 0);
    const maxAttempts = Number(data.max_attempts ?? 0);
    const errorType = getString(data.error_type);
    const errorMessage = getString(data.error_message) || "上游请求失败";
    const id = `retry:${sessionId}`;
    return {
      id,
      correlation_id: id,
      type: "retry",
      role: "system",
      status: "running",
      display: "list",
      agent: node,
      content: errorMessage,
      payload: {
        node,
        attempt,
        max_attempts: maxAttempts,
        error_type: errorType,
        error_message: errorMessage,
      },
    };
  }

  if (eventName === "agent:usage") {
    return {
      type: "token_usage",
      role: "system",
      display: "hidden",
      payload: {
        session_id: getString(data.session_id),
        token_input: Number(data.token_input ?? 0),
        token_output: Number(data.token_output ?? 0),
        token_cache: Number(data.token_cache ?? 0),
        context_input_tokens: Number(data.context_input_tokens ?? data.token_input ?? 0),
        context_length: Number(data.context_length ?? 128000),
      },
    };
  }

  if (eventName === "agent:task_usage_snapshot" || eventName === "agent:task_usage_delta") {
    return {
      type: eventName === "agent:task_usage_snapshot" ? "task_usage_snapshot" : "task_usage_delta",
      role: "system",
      display: "hidden",
      payload: {
        session_id: getString(data.session_id),
        task_id: getString(data.task_id),
        token_input: Number(data.token_input ?? 0),
        token_output: Number(data.token_output ?? 0),
        token_cache: Number(data.token_cache ?? 0),
      },
    };
  }

  if (eventName === "agent:task_title_updated") {
    return {
      type: "task_title_updated",
      role: "system",
      display: "hidden",
      payload: {
        task_id: getString(data.task_id),
        project_id: getString(data.project_id),
        chapter_id: getString(data.chapter_id),
        title: getString(data.title),
        updated_at: getString(data.updated_at),
      },
    };
  }

  if (eventName === "agent:chapter_refresh") {
    return {
      type: "chapter_refresh",
      role: "system",
      status: "completed",
      display: "hidden",
      created_at: getString(data.created_at),
      payload: {
        session_id: getString(data.session_id),
        project_id: getString(data.project_id),
        chapter_id: getString(data.chapter_id),
      },
    };
  }

  if (eventName === "agent:note_refresh") {
    return {
      type: "note_refresh",
      role: "system",
      status: "completed",
      display: "hidden",
      created_at: getString(data.created_at),
      payload: {
        session_id: getString(data.session_id),
        project_id: getString(data.project_id),
        note_id: getString(data.note_id),
      },
    };
  }

  if (eventName === "agent:compaction_start") {
    const compactionId = getString(data.compaction_id);
    const sessionKey = getString(data.session_id) || sessionId;
    const startSeq = Number(data.start_seq ?? 0);
    const endSeq = Number(data.end_seq ?? 0);
    const id = compactionId
      ? `compaction:${compactionId}`
      : `compaction:${sessionKey}:${startSeq}:${endSeq}:pending`;
    return {
      id,
      correlation_id: id,
      type: "compaction",
      role: "system",
      status: "running",
      display: "list",
      content: "正在压缩上下文",
      created_at: getString(data.created_at),
      payload: {
        session_id: sessionKey,
        trigger: getString(data.trigger),
        compaction_id: compactionId,
        start_seq: startSeq,
        end_seq: endSeq,
        source_input_tokens: Number(data.source_input_tokens ?? 0),
      },
    };
  }

  if (eventName === "agent:compaction_success") {
    const compactionId = getString(data.compaction_id);
    const id = compactionId
      ? `compaction:${compactionId}`
      : `compaction:${getString(data.session_id) || sessionId}:${Number(data.start_seq ?? 0)}:${Number(data.end_seq ?? 0)}`;
    return {
      id,
      correlation_id: id,
      type: "compaction",
      role: "system",
      status: "completed",
      display: "list",
      content: "上下文已压缩",
      created_at: getString(data.created_at),
      payload: {
        session_id: getString(data.session_id) || sessionId,
        compaction_id: compactionId,
        trigger: getString(data.trigger),
        start_seq: Number(data.start_seq ?? 0),
        end_seq: Number(data.end_seq ?? 0),
        source_input_tokens: Number(data.source_input_tokens ?? 0),
        summary_tokens: Number(data.summary_tokens ?? 0),
      },
    };
  }

  if (eventName === "agent:compaction_error") {
    const code = getString(data.code) || getString(data.error_code);
    const message = getString(data.message) || getString(data.reason) || getString(data.error) || "压缩失败";
    const id = `compaction:error:${getString(data.session_id) || sessionId}:${Date.now()}`;
    return {
      id,
      correlation_id: id,
      type: "compaction_error",
      role: "system",
      status: "error",
      display: "hidden",
      content: message,
      created_at: getString(data.created_at),
      payload: {
        session_id: getString(data.session_id) || sessionId,
        code,
        message,
        trigger: getString(data.trigger),
      },
    };
  }

  if (eventName === "agent:done") {
    return {
      type: "task_completed",
      role: "system",
      status: "completed",
      display: "hidden",
      created_at: getString(data.created_at),
      payload: {},
    };
  }

  if (eventName === "agent:error") {
    if (data.type === "invalid_session") return null;
    const content = getString(data.reason) || getString(data.error) || getString(data.message) || "Agent 运行失败";
    return {
      type: "error",
      role: "system",
      status: "error",
      display: "list",
      content,
      payload: data,
    };
  }

  if (eventName === "agent:interrupt") {
    if (data.type === "ask_user") {
      const actionId = getString(data.action_id) || getString(data.id) || `question-${Date.now()}`;
      return {
        id: actionId,
        correlation_id: actionId,
        type: "question",
        role: "system",
        status: "pending",
        display: "panel",
        payload: {
          action_id: actionId,
          questions: Array.isArray(data.questions) ? data.questions : [],
        },
      };
    }

    if (data.type === "tool_approval") {
      const approvalId = getString(data.approval_id) || getString(data.id) || `approval-${Date.now()}`;
      const toolArgs = isRecord(data.args)
        ? data.args
        : isRecord(data.tool_args)
          ? data.tool_args
          : {};
      const toolName = getString(data.tool_name) || "";
      const toolCallId = getString(data.tool_call_id);
      const toolResultPreview = isRecord(data.tool_result_preview)
        ? data.tool_result_preview
        : undefined;
      return {
        id: approvalId,
        correlation_id: approvalId,
        type: "approval",
        role: "system",
        status: "pending",
        display: "panel",
        approval_id: approvalId,
        tool_name: toolName,
        tool_call_id: toolCallId,
        tool_args: toolArgs,
        tool_result_preview: toolResultPreview,
        message: getString(data.message) || `是否允许调用 ${toolName}？`,
        interrupt_behavior: data.interrupt_behavior === "cancel" ? "cancel" : "block",
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
  }

  return null;
}
