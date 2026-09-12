/**
 * World Info Types
 *
 * Definisi tipe terkait buku dunia.
 */

// ============================================
// Tipe buku dunia
// ============================================

/** Buku dunia */
export interface WorldInfo {
  id: string;
  projectId: string | null;
  createdAt: string;
  updatedAt: string;
}

// ============================================
// Tipe entri buku dunia
// ============================================

/** Entri buku dunia (lengkap, dipakai untuk penyuntingan) */
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

/** Entri buku dunia versi ringan (dipakai untuk daftar, tanpa content) */
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

/** Permintaan pembuatan entri */
export interface WorldInfoEntryCreate {
  name: string;
  content?: string;
  tokenCount?: number;
  isEnabled?: boolean;
}

/** Permintaan pembaruan entri */
export interface WorldInfoEntryUpdate {
  name?: string;
  content?: string;
  tokenCount?: number;
  isEnabled?: boolean;
}

/** Respons daftar entri versi ringan */
export interface WorldInfoEntryBriefListResponse {
  items: WorldInfoEntryBrief[];
  total: number;
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
// Tipe pencarian
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
