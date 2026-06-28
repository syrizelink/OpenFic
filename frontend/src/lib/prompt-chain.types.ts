/**
 * Prompt Chain Types
 *
 * 提示词链相关类型定义
 */

export interface PromptEntryData {
  id?: string;
  uid?: string;  // 跨版本追踪标识符
  name: string;
  role: "system" | "user" | "assistant";
  content: string;
  order_index: number;
  is_enabled: boolean;
  token_count: number;
}

export interface PromptChainVersion {
  id: string;
  modeName: string;
  taskName: string;
  agentName: string | null;
  versionHash: string;
  versionNumber: number;
  parentVersionId: string | null;
  isActive: boolean;
  note: string | null;
  createdAt: string;
}

export interface PromptEntry {
  id: string;
  uid: string;  // 跨版本追踪标识符
  versionId: string;
  name: string;
  role: "system" | "user" | "assistant";
  content: string;
  orderIndex: number;
  isEnabled: boolean;
  tokenCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface VersionWithEntries {
  version: PromptChainVersion;
  entries: PromptEntry[];
}

export interface CreateVersionRequest {
  parentVersionId: string;
  entries: PromptEntryData[];
  note?: string;
}

export interface AgentMetadata {
  value: string;
}

export interface TaskMetadata {
  value: string;
  agents: AgentMetadata[];
}

export interface ModeMetadata {
  value: string;
  tasks: TaskMetadata[];
}

export interface PromptChainsMetadata {
  modes: ModeMetadata[];
}

export interface CompileRequest {
  project_id?: string | null;
  chapter_id?: string | null;
}

export interface CompiledEntry {
  role: string;
  content: string;
  token_count: number;
}

export interface CompileResponse {
  entries: CompiledEntry[];
  total_tokens: number;
}

// ============ 版本差异对比相关 ============

export interface EntryDiff {
  entryId: string;
  changeType: "added" | "deleted" | "modified";
  baseEntry: PromptEntry | null;
  compareEntry: PromptEntry | null;
}

export interface VersionDiff {
  baseVersion: PromptChainVersion;
  compareVersion: PromptChainVersion;
  diffs: EntryDiff[];
}

