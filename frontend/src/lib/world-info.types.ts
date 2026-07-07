/**
 * World Info Types
 *
 * 世界书相关类型定义。
 */

// ============================================
// 世界书类型
// ============================================

/** 世界书 */
export interface WorldInfo {
  id: string;
  projectId: string | null;
  createdAt: string;
  updatedAt: string;
}

// ============================================
// 世界书条目类型
// ============================================

/** 世界书条目（完整，编辑用） */
export interface WorldInfoEntry {
  id: string;
  worldInfoId: string;
  uid: number;
  name: string;
  order: number;
  content: string;
  tokenCount: number;
  isEnabled: boolean;
  createdAt: string;
  updatedAt: string;
}

/** 世界书条目轻量（列表用，不含 content） */
export interface WorldInfoEntryBrief {
  id: string;
  worldInfoId: string;
  uid: number;
  name: string;
  order: number;
  tokenCount: number;
  isEnabled: boolean;
  createdAt: string;
  updatedAt: string;
}

/** 创建条目请求 */
export interface WorldInfoEntryCreate {
  name: string;
  content?: string;
  tokenCount?: number;
  isEnabled?: boolean;
}

/** 更新条目请求 */
export interface WorldInfoEntryUpdate {
  name?: string;
  content?: string;
  tokenCount?: number;
  isEnabled?: boolean;
}

/** 条目轻量列表响应 */
export interface WorldInfoEntryBriefListResponse {
  items: WorldInfoEntryBrief[];
  total: number;
  page: number;
  pageSize: number;
}

/** 条目列表请求参数 */
export interface WorldInfoEntryListParams {
  page?: number;
  pageSize?: number;
}

export interface WorldInfoImportPreviewEntry {
  uid: number;
  name: string;
  contentPreview: string;
  isEnabled: boolean;
}

export interface WorldInfoImportPreviewResponse {
  entryCount: number;
  enabledCount: number;
  entries: WorldInfoImportPreviewEntry[];
}

export type WorldInfoImportMode = "append" | "overwrite";

export interface WorldInfoImportProgressEvent {
  type: "progress";
  stage: "reading" | "parsing" | "importing_entries";
  progress: number;
  current?: number;
  total?: number;
}

export interface WorldInfoImportCompleteEvent {
  type: "complete";
  world_info_id: string;
  imported_count: number;
}

export interface WorldInfoImportErrorEvent {
  type: "error";
  message: string;
}

export type WorldInfoImportEvent =
  | WorldInfoImportProgressEvent
  | WorldInfoImportCompleteEvent
  | WorldInfoImportErrorEvent;

// ============================================
// 搜索类型
// ============================================

export interface WorldInfoEntrySearchMatch {
  lineNumber: number;
  lineText: string;
}

export interface WorldInfoEntrySearchResult {
  entryId: string;
  entryName: string;
  uid: number;
  matches: WorldInfoEntrySearchMatch[];
}

export interface WorldInfoEntrySearchResponse {
  results: WorldInfoEntrySearchResult[];
  totalEntries: number;
  totalMatches: number;
}
