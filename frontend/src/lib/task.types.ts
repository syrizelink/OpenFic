/**
 * Task Types
 *
 * 任务相关类型定义。
 */

/** 任务消息 */
export interface TaskMessage {
  id: string;
  taskId?: string | null;
  role: "system" | "user" | "assistant" | "tool";
  agentId?: string | null;
  content: string;
  toolCalls?: Record<string, unknown>[];
  toolCallId?: string | null;
  metadata?: Record<string, unknown> | null;
  messageType?: string | null;
  messageStatus?: string | null;
  displayChannel?: string | null;
  payload?: Record<string, unknown> | null;
  correlationId?: string | null;
  createdAt: string;
  updatedAt?: string;
}

/** 任务列表项 */
export interface TaskListItem {
  id: string;
  projectId: string;
  title: string;
  tokenInput: number;
  tokenOutput: number;
  tokenCache: number;
  contextInputTokens: number;
  isRunning: boolean;
  isFavorited: boolean;
  createdAt: string;
  updatedAt: string;
}

/** 任务详情 */
export interface Task {
  id: string;
  projectId: string;
  title: string;
  messages: TaskMessage[];
  tokenInput: number;
  tokenOutput: number;
  tokenCache: number;
  contextInputTokens: number;
  isRunning: boolean;
  currentRevisionId?: string | null;
  currentMessageId?: string | null;
  agentSessionId?: string | null;
  isFavorited: boolean;
  createdAt: string;
  updatedAt: string;
}

/** 任务列表响应 */
export interface TaskListResponse {
  items: TaskListItem[];
  total: number;
}

/** 更新任务请求 */
export interface UpdateTaskRequest {
  title?: string;
  is_favorited?: boolean;
}
