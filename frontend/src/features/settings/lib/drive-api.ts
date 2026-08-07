/**
 * Google Drive 同步 API。
 */

import { apiClient } from "@/lib/api-client";

import type {
  DriveAuthUrlResponse,
  DriveConfig,
  DriveConfigUpdate,
  DriveProjectStatus,
  DriveSyncResult,
} from "./drive.types";

function transformConfig(raw: Record<string, unknown>): DriveConfig {
  return {
    hasCredentials: Boolean(raw.has_credentials),
    connected: Boolean(raw.connected),
    email: (raw.email as string | null) ?? null,
    folderId: (raw.folder_id as string | null) ?? null,
    intervalMinutes: Number(raw.interval_minutes ?? 0),
    redirectUri: (raw.redirect_uri as string) || "",
  };
}

export async function fetchDriveConfig(): Promise<DriveConfig> {
  const response = await apiClient.get("/drive/config");
  return transformConfig(response.data);
}

export async function updateDriveConfig(data: DriveConfigUpdate): Promise<DriveConfig> {
  const response = await apiClient.put("/drive/config", {
    client_id: data.clientId,
    client_secret: data.clientSecret,
    interval_minutes: data.intervalMinutes,
  });
  return transformConfig(response.data);
}

export async function fetchDriveAuthUrl(): Promise<DriveAuthUrlResponse> {
  const response = await apiClient.get("/drive/auth-url");
  return {
    authUrl: response.data.auth_url as string,
    redirectUri: response.data.redirect_uri as string,
  };
}

export async function disconnectDrive(): Promise<DriveConfig> {
  const response = await apiClient.delete("/drive/connection");
  return transformConfig(response.data);
}

function transformProjectStatus(raw: Record<string, unknown>): DriveProjectStatus {
  return {
    projectId: raw.project_id as string,
    projectTitle: (raw.project_title as string) || "",
    connected: Boolean(raw.connected),
    enabled: Boolean(raw.enabled),
    fileId: (raw.file_id as string | null) ?? null,
    docUrl: (raw.doc_url as string | null) ?? null,
    lastSyncedAt: (raw.last_synced_at as string | null) ?? null,
    chapterCount: Number(raw.chapter_count ?? 0),
    wordCount: Number(raw.word_count ?? 0),
    errorMessage: (raw.error_message as string | null) ?? null,
  };
}

export async function fetchDriveProjectStatus(projectId: string): Promise<DriveProjectStatus> {
  const response = await apiClient.get(`/drive/projects/${projectId}`);
  return transformProjectStatus(response.data);
}

export async function updateDriveProjectStatus(
  projectId: string,
  enabled: boolean,
): Promise<DriveProjectStatus> {
  const response = await apiClient.put(`/drive/projects/${projectId}`, { enabled });
  return transformProjectStatus(response.data);
}

function transformSyncResult(raw: Record<string, unknown>): DriveSyncResult {
  return {
    projectId: raw.project_id as string,
    status: raw.status as DriveSyncResult["status"],
    fileId: (raw.file_id as string | null) ?? null,
    docName: (raw.doc_name as string | null) ?? null,
    docUrl: (raw.doc_url as string | null) ?? null,
    chapterCount: Number(raw.chapter_count ?? 0),
    wordCount: Number(raw.word_count ?? 0),
    syncedAt: (raw.synced_at as string | null) ?? null,
    message: (raw.message as string | null) ?? null,
  };
}

export async function syncDriveProject(projectId: string): Promise<DriveSyncResult> {
  const response = await apiClient.post(`/drive/projects/${projectId}/sync`);
  return transformSyncResult(response.data);
}
