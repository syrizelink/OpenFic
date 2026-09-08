/**
 * 导入 API - 项目文件导入相关接口。
 */

import axios from "axios";

import i18n from "@/i18n";
import { apiClient, getApiBaseUrl, handleAuthenticationFailure } from "@/lib/api-client";

/** 预览章节信息 */
export interface PreviewChapter {
  title: string;
  word_count: number;
  content_preview: string;
}

/** 预览卷信息 */
export interface PreviewVolume {
  title: string;
  chapter_count: number;
  chapters: PreviewChapter[];
}

/** 导入预览响应 */
export interface ImportPreviewResponse {
  volumes: PreviewVolume[];
  total_word_count: number;
  chapter_count: number;
  detected_encoding: string;
}

export type ImportSplitMode = "auto" | "manual";
export type ImportStructureMode = "separate_volumes" | "merge_volume";
export type ChapterTitleMode = "preserve" | "continuous_numbering";

/** Shared parsing options for one or more imported documents. */
export interface DocumentImportOptions {
  splitMode: ImportSplitMode;
  chunkSize: number;
  structureMode: ImportStructureMode;
  mergedVolumeTitle: string;
  chapterTitleMode: ChapterTitleMode;
}

/** Metadata used when imported documents create a new project. */
export interface DocumentProjectInfo {
  title: string;
  description?: string;
  cover?: File | null;
}

export type DocumentImportPlacement =
  | { placement: "append" }
  | { placement: "after_volume"; afterVolumeId: string };

export const DEFAULT_IMPORT_CHUNK_SIZE = 800;
export const MAX_IMPORT_CHUNK_SIZE = 100_000;
export const MAX_MERGED_VOLUME_TITLE_LENGTH = 200;

export const DEFAULT_DOCUMENT_IMPORT_OPTIONS: DocumentImportOptions = {
  splitMode: "auto",
  chunkSize: DEFAULT_IMPORT_CHUNK_SIZE,
  structureMode: "separate_volumes",
  mergedVolumeTitle: "",
  chapterTitleMode: "preserve",
};

export type DocumentImportOptionsValidationKey =
  | "import.invalidChunkSize"
  | "import.documents.mergedVolumeTitleRequired"
  | "import.documents.mergedVolumeTitleTooLong";

/** Return an i18n key for invalid options, or null when they can be submitted. */
export function validateDocumentImportOptions(
  options: DocumentImportOptions,
): DocumentImportOptionsValidationKey | null {
  if (
    options.splitMode === "manual" &&
    (!Number.isInteger(options.chunkSize) ||
      options.chunkSize < 1 ||
      options.chunkSize > MAX_IMPORT_CHUNK_SIZE)
  ) {
    return "import.invalidChunkSize";
  }

  if (options.structureMode === "merge_volume") {
    const mergedVolumeTitle = options.mergedVolumeTitle.trim();
    if (!mergedVolumeTitle) return "import.documents.mergedVolumeTitleRequired";
    if (mergedVolumeTitle.length > MAX_MERGED_VOLUME_TITLE_LENGTH) {
      return "import.documents.mergedVolumeTitleTooLong";
    }
  }

  return null;
}

/** 确认导入响应 */
export interface ImportConfirmResponse {
  project_id: string;
  title: string;
  chapter_count: number;
  total_word_count: number;
}

/** Result returned after importing documents into an existing project. */
export interface ProjectChapterImportResponse {
  first_chapter_id: string;
  created_volume_ids: string[];
  chapter_count: number;
  total_word_count: number;
}

function buildDocumentImportFormData(files: File[], options: DocumentImportOptions): FormData {
  const formData = new FormData();

  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("split_mode", options.splitMode);
  formData.append(
    "chunk_size",
    String(options.splitMode === "manual" ? options.chunkSize : DEFAULT_IMPORT_CHUNK_SIZE),
  );
  formData.append("structure_mode", options.structureMode);
  formData.append("chapter_title_mode", options.chapterTitleMode);

  if (options.structureMode === "merge_volume") {
    formData.append("merged_volume_title", options.mergedVolumeTitle.trim());
  }

  return formData;
}

interface ApiErrorPayload {
  detail?: unknown;
}

/** Extract FastAPI's business-error detail from document import requests. */
export function getDocumentImportErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return error instanceof Error ? error.message : fallback;
}

/** Preview one or more documents in their submitted order. */
export async function previewDocuments(
  files: File[],
  options: DocumentImportOptions,
): Promise<ImportPreviewResponse> {
  const response = await apiClient.post<ImportPreviewResponse>(
    "/import/documents/preview",
    buildDocumentImportFormData(files, options),
    { headers: { "Content-Type": "multipart/form-data" } },
  );

  return response.data;
}

/** Create a project from one or more documents in their submitted order. */
export async function confirmDocumentProject(
  files: File[],
  projectInfo: DocumentProjectInfo,
  options: DocumentImportOptions,
): Promise<ImportConfirmResponse> {
  const formData = buildDocumentImportFormData(files, options);
  formData.append("title", projectInfo.title);

  if (projectInfo.description) {
    formData.append("description", projectInfo.description);
  }
  if (projectInfo.cover) {
    formData.append("cover", projectInfo.cover);
  }

  const response = await apiClient.post<ImportConfirmResponse>(
    "/import/documents/confirm",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
    },
  );

  return response.data;
}

/** Import one or more documents into an existing project. */
export async function importDocumentsIntoProject(
  projectId: string,
  files: File[],
  placement: DocumentImportPlacement,
  options: DocumentImportOptions,
): Promise<ProjectChapterImportResponse> {
  const formData = buildDocumentImportFormData(files, options);
  formData.append("placement", placement.placement);

  if (placement.placement === "after_volume") {
    formData.append("after_volume_id", placement.afterVolumeId);
  }

  const response = await apiClient.post<ProjectChapterImportResponse>(
    `/projects/${projectId}/chapter-imports`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );

  return response.data;
}

/**
 * 预览项目文件解析结果。
 *
 * @param file TXT、Markdown 或 ZIP 文件
 * @returns 解析预览结果
 */
export async function previewImportFile(
  file: File,
  splitMode: ImportSplitMode = "auto",
  chunkSize = DEFAULT_IMPORT_CHUNK_SIZE,
): Promise<ImportPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("split_mode", splitMode);
  formData.append("chunk_size", String(chunkSize));

  const response = await apiClient.post<ImportPreviewResponse>("/import/preview", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return response.data;
}

/**
 * 确认导入，创建项目和章节。
 *
 * @param file TXT、Markdown 或 ZIP 文件
 * @param title 书名
 * @param description 简介（可选）
 * @param cover 封面文件（可选）
 * @param splitMode 分割模式
 * @param chunkSize 手动分割时的每章字数
 * @returns 导入结果
 */
export async function confirmImport(
  file: File,
  title: string,
  description?: string,
  cover?: File | null,
  splitMode: ImportSplitMode = "auto",
  chunkSize = DEFAULT_IMPORT_CHUNK_SIZE,
): Promise<ImportConfirmResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);
  formData.append("split_mode", splitMode);
  formData.append("chunk_size", String(chunkSize));

  if (description) {
    formData.append("description", description);
  }

  if (cover) {
    formData.append("cover", cover);
  }

  const response = await apiClient.post<ImportConfirmResponse>("/import/confirm", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return response.data;
}

/** 导入进度事件 */
export interface ImportProgressEvent {
  type: "progress";
  stage: "reading" | "parsing" | "creating_project" | "saving_chapters";
  progress: number;
  current?: number;
  total?: number;
}

/** 导入完成事件 */
export interface ImportCompleteEvent {
  type: "complete";
  project_id: string;
  title: string;
  chapter_count: number;
  total_word_count: number;
}

/** 导入错误事件 */
export interface ImportErrorEvent {
  type: "error";
  message: string;
}

/** 导入事件类型 */
export type ImportEvent = ImportProgressEvent | ImportCompleteEvent | ImportErrorEvent;

/**
 * 流式确认导入，提供实时进度更新。
 *
 * @param file TXT、Markdown 或 ZIP 文件
 * @param title 书名
 * @param description 简介（可选）
 * @param cover 封面文件（可选）
 * @param splitMode 分割模式
 * @param chunkSize 手动分割时的每章字数
 * @param onEvent 事件回调
 */
export async function confirmImportStream(
  file: File,
  title: string,
  description: string | undefined,
  cover: File | null | undefined,
  splitMode: ImportSplitMode,
  chunkSize: number,
  onEvent: (event: ImportEvent) => void,
): Promise<ImportConfirmResponse | null> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);
  formData.append("split_mode", splitMode);
  formData.append("chunk_size", String(chunkSize));

  if (description) {
    formData.append("description", description);
  }

  if (cover) {
    formData.append("cover", cover);
  }

  const response = await fetch(`${getApiBaseUrl()}/import/confirm-stream`, {
    method: "POST",
    body: formData,
    credentials: "include",
  });

  if (!response.ok) {
    if (response.status === 401) handleAuthenticationFailure();
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error(i18n.t("import.streamUnavailable"));
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let result: ImportConfirmResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // 解析 SSE 事件
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event = JSON.parse(line.slice(6)) as ImportEvent;
          onEvent(event);

          if (event.type === "complete") {
            result = {
              project_id: event.project_id,
              title: event.title,
              chapter_count: event.chapter_count,
              total_word_count: event.total_word_count,
            };
          } else if (event.type === "error") {
            throw new Error(event.message);
          }
        } catch (e) {
          if (e instanceof SyntaxError) {
            console.warn("无法解析 SSE 事件:", line);
          } else {
            throw e;
          }
        }
      }
    }
  }

  return result;
}
