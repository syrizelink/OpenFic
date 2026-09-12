/**
 * Task Types
 *
 * Definisi tipe terkait tugas.
 */

/** Pesan tugas */
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

/** Item daftar tugas */
export interface TaskListItem {
  id: string;
  projectId: string;
  title: string;
  tokenInput: number;
  tokenOutput: number;
  tokenCache: number;
  contextInputTokens: number;
  cost: number;
  isRunning: boolean;
  isFavorited: boolean;
  createdAt: string;
  updatedAt: string;
}

/** Detail tugas */
export interface Task {
  id: string;
  projectId: string;
  title: string;
  messages: TaskMessage[];
  tokenInput: number;
  tokenOutput: number;
  tokenCache: number;
  contextInputTokens: number;
  cost: number;
  isRunning: boolean;
  currentRevisionId?: string | null;
  currentMessageId?: string | null;
  agentSessionId?: string | null;
  isFavorited: boolean;
  createdAt: string;
  updatedAt: string;
}

/** Respons daftar tugas */
export interface TaskListResponse {
  items: TaskListItem[];
  total: number;
}

/** Permintaan pembaruan tugas */
export interface UpdateTaskRequest {
  title?: string;
  is_favorited?: boolean;
}
