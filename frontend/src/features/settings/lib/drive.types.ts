/**
 * Google Drive 同步类型定义。
 */

export interface DriveConfig {
  hasCredentials: boolean;
  connected: boolean;
  email: string | null;
  folderId: string | null;
  intervalMinutes: number;
  redirectUri: string;
}

export interface DriveConfigUpdate {
  clientId?: string;
  clientSecret?: string;
  intervalMinutes?: number;
}

export interface DriveAuthUrlResponse {
  authUrl: string;
  redirectUri: string;
}

export interface DriveProjectStatus {
  projectId: string;
  projectTitle: string;
  connected: boolean;
  enabled: boolean;
  fileId: string | null;
  docUrl: string | null;
  lastSyncedAt: string | null;
  chapterCount: number;
  wordCount: number;
  errorMessage: string | null;
}

export type DriveSyncStatus = "synced" | "unchanged" | "error";

export interface DriveSyncResult {
  projectId: string;
  status: DriveSyncStatus;
  fileId: string | null;
  docName: string | null;
  docUrl: string | null;
  chapterCount: number;
  wordCount: number;
  syncedAt: string | null;
  message: string | null;
}
