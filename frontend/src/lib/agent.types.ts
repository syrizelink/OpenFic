/**
 * Agent Types
 *
 * Agent 工作流相关类型定义
 */

import type { TaskMessage } from "./task.types";

export type AgentType =
  | "primary"
  | "explorer"
  | "composer"
  | "auditor"
  | "writer"
  | "actor"
  | "reviewer";

export type SubagentDispatchStatus =
  | "queued"
  | "running"
  | "waiting_user"
  | "completed"
  | "error"
  | "cancelled";

export type SubagentDispatchMode = "sync" | "async";

export interface ActiveSubagentState {
  childRunId: string;
  childThreadId: string;
  agentKey: AgentType;
  agentNumber?: string;
  status: SubagentDispatchStatus;
  queuedMessages: number;
  isActive: boolean;
  pendingApproval?: Record<string, unknown> | null;
}

export interface SubagentSessionPayload {
  childRunId: string;
  childThreadId: string;
  parentSessionId: string;
  agentKey: AgentType;
  agentNumber?: string;
  status: SubagentDispatchStatus;
  isActive: boolean;
  isRunning: boolean;
  tokenInput: number;
  tokenOutput: number;
  tokenCache: number;
  contextInputTokens: number;
  contextLength: number;
  pendingApproval?: Record<string, unknown> | null;
  messages: TaskMessage[];
}

export interface ParentConversationDescriptor {
  kind: "parent";
  sessionId: string;
}

export interface SubagentConversationDescriptor {
  kind: "subagent";
  childRunId: string;
  childThreadId: string;
  parentSessionId: string;
}

export type AgentConversationDescriptor =
  | ParentConversationDescriptor
  | SubagentConversationDescriptor;

export type AgentMessageType =
  | "text"
  | "retry"
  | "reasoning"
  | "tool"
  | "approval"
  | "question"
  | "compaction"
  | "node_start"
  | "node_end"
  | "stage_start"
  | "stage_transfer"
  | "token_usage"
  | "task_usage_snapshot"
  | "task_usage_delta"
  | "chapter_refresh"
  | "note_refresh"
  | "world_entry_refresh"
  | "task_completed"
  | "user_request"
  | "agent_thinking"
  | "agent_output"
  | "confirmed_plan"
  | "clarification"
  | "outline"
  | "content"
  | "review"
  | "iteration"
  | "tool_call"
  | "tool_approval"
  | "completed"
  | "error";

export interface ConfirmedPlan {
  understanding: string;
  target: string;
  additional_info: string;
}

export interface ClarificationOption {
  label: string;
  description?: string;
}

export interface ClarificationQuestion {
  title: string;
  description?: string;
  options: ClarificationOption[];
}

export interface TokenUsageState {
  tokenInput: number;
  tokenOutput: number;
  tokenCache: number;
  contextInputTokens: number;
  contextLength: number;
}

export interface OutlineBeatData {
  content: string;
  tone?: string;
  note?: string;
}

export interface OutlineData {
  beats: OutlineBeatData[];
}

export interface ReviewIssueData {
  severity: "minor" | "major" | "critical";
  description: string;
  suggestion: string;
}

export interface ReviewData {
  passed: boolean;
  feedback: string;
  issues: ReviewIssueData[];
  revision_focus: string[];
}

export interface ToolApprovalData {
  approval_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  message: string;
  interrupt_behavior: "cancel" | "block";
  tool_call_id?: string;
  tool_result_preview?: Record<string, unknown>;
}

export interface AgentMessage {
  id: string;
  type: AgentMessageType;
  timestamp: number;
  role?: "user" | "assistant" | "system" | "tool";
  status?: "pending" | "running" | "completed" | "error";
  display?: "list" | "panel" | "hidden";
  payload?: Record<string, unknown>;
  correlationId?: string | null;

  revisionId?: string;
  isCheckpoint?: boolean;

  content?: string;
  agent?: AgentType;
  isDraft?: boolean;

  questions?: ClarificationQuestion[];
  confirmedPlan?: ConfirmedPlan;
  outlineData?: OutlineData;

  iteration?: number;
  maxIterations?: number;

  reviewPassed?: boolean;
  reviewData?: ReviewData;

  finalContent?: string;
  wordCount?: number;

  toolName?: string;
  toolNames?: string[];
  toolArgs?: Record<string, unknown>;
  toolArgsText?: string;
  partialToolArgs?: Record<string, unknown>;
  toolResult?: Record<string, unknown>;
  toolSuccess?: boolean;
  toolApproval?: ToolApprovalData;

  isStreaming?: boolean;
  thinkingDurationMs?: number;
}

export type AgentSessionStatus =
  | "idle"
  | "running"
  | "waiting_answer"
  | "waiting_approval"
  | "completed"
  | "error";

export interface AgentSession {
  sessionId: string;
  projectId: string;
  status: AgentSessionStatus;
  messages: AgentMessage[];
  currentAgent?: AgentType;
  iterationCount: number;
  maxIterations: number;
  clarificationQuestions?: ClarificationQuestion[];
  finalContent?: string;
  error?: string;
}

export interface AgentSessionCreateRequest {
  project_id: string;
  model_id: string;
  max_iterations?: number;
  agent_key?: string;
}

export interface AgentSessionCreateResponse {
  session_id: string;
  project_id: string;
  status: string;
  task_id: string;
  task_title: string;
  task_created_at: string;
  task_updated_at: string;
}

export interface AgentForkResponse {
  session_id: string;
  task_id: string;
  task_title: string;
  task_created_at: string;
  task_updated_at: string;
}

export interface AgentSessionStateResponse {
  sessionId: string;
  state: Record<string, unknown>;
  isRunning: boolean;
}

export interface AgentSendMessageRequest {
  message: string;
}

export type AgentPendingMessageAction = "queued" | "cancelled" | "consumed";

export interface AgentPendingMessage {
  messageId: string;
  content: string;
  createdAt: string;
}

export interface AgentSendMessageResponse {
  success: boolean;
  session_id: string;
  message: string;
  queued: boolean;
  pending_message: AgentPendingMessage | null;
}

export interface AgentCompactionResponse {
  success: boolean;
  session_id: string;
  compaction_id: string;
  start_seq: number;
  end_seq: number;
  source_input_tokens: number;
  summary_tokens: number;
}

export interface AgentEvent {
  type: string;
  id?: string;
  role?: "user" | "assistant" | "system" | "tool";
  status?: "pending" | "running" | "completed" | "error";
  display?: "list" | "panel" | "hidden";
  payload?: Record<string, unknown>;
  correlation_id?: string | null;
  created_at?: string;
  updated_at?: string;
  agent?: string;
  owner_agent?: string;
  stage?: string;
  content?: string;
  questions?: ClarificationQuestion[];
  confirmed_plan?: ConfirmedPlan;
  outline?: string;
  outline_data?: OutlineData;
  review_data?: ReviewData;
  review_passed?: boolean;
  iteration?: number;
  max_iterations?: number;
  final_content?: string;
  word_count?: number;
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  tool_result?: Record<string, unknown>;
  tool_call_id?: string;
  tool_result_preview?: Record<string, unknown>;
  success?: boolean;
  approval_id?: string;
  message?: string;
  interrupt_behavior?: "cancel" | "block";
  error?: string;
  error_type?: string;
  error_node?: string;
  error_status_code?: number;
  message_id?: string;
  revision_id?: string;
  is_checkpoint?: boolean;
  isCheckpoint?: boolean;
  is_continuation?: boolean;
}

export interface AgentQuestionAnswerResponse {
  success?: boolean;
  session_id?: string;
  message?: string;
}

export interface AgentRollbackResponse {
  success: boolean;
  session_id: string;
  revision_id: string | null;
  affected_chapters: string[];
  affected_notes: string[];
  affected_note_categories: string[];
  affected_world_entries: string[];
  restored_message_content: string;
}

export interface AgentCancelResponse {
  success: boolean;
  session_id: string;
  message: string;
}

export interface AgentCancelPendingMessageResponse {
  success: boolean;
  session_id: string;
  message_id: string;
  restored_message_content: string;
}

export interface AgentToolApprovalResponse {
  success?: boolean;
  session_id?: string;
  message?: string;
}
