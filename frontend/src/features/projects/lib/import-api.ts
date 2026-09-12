/**
 * API impor - antarmuka terkait impor berkas proyek.
 */

import i18n from "@/i18n";
import { apiClient, getApiBaseUrl, handleAuthenticationFailure } from "@/lib/api-client";

/** Informasi pratinjau bab */
export interface PreviewChapter {
  title: string;
  word_count: number;
  content_preview: string;
}

/** Informasi pratinjau volume */
export interface PreviewVolume {
  title: string;
  chapter_count: number;
  chapters: PreviewChapter[];
}

/** Respons pratinjau impor */
export interface ImportPreviewResponse {
  volumes: PreviewVolume[];
  total_word_count: number;
  chapter_count: number;
  detected_encoding: string;
}

export type ImportSplitMode = "auto" | "manual";

export const DEFAULT_IMPORT_CHUNK_SIZE = 800;
export const MAX_IMPORT_CHUNK_SIZE = 100_000;

/** Respons konfirmasi impor */
export interface ImportConfirmResponse {
  project_id: string;
  title: string;
  chapter_count: number;
  total_word_count: number;
}

/**
 * Melihat pratinjau hasil penguraian berkas proyek.
 *
 * @param file Berkas TXT, Markdown, atau ZIP
 * @returns Hasil pratinjau penguraian
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
 * Mengonfirmasi impor, membuat proyek dan bab.
 *
 * @param file Berkas TXT, Markdown, atau ZIP
 * @param title Judul buku
 * @param description Deskripsi (opsional)
 * @param cover Berkas sampul (opsional)
 * @param splitMode Mode pemisahan
 * @param chunkSize Jumlah kata per bab saat pemisahan manual
 * @returns Hasil impor
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

/** Peristiwa progres impor */
export interface ImportProgressEvent {
  type: "progress";
  stage: "reading" | "parsing" | "creating_project" | "saving_chapters";
  progress: number;
  current?: number;
  total?: number;
}

/** Peristiwa impor selesai */
export interface ImportCompleteEvent {
  type: "complete";
  project_id: string;
  title: string;
  chapter_count: number;
  total_word_count: number;
}

/** Peristiwa galat impor */
export interface ImportErrorEvent {
  type: "error";
  message: string;
}

/** Tipe peristiwa impor */
export type ImportEvent = ImportProgressEvent | ImportCompleteEvent | ImportErrorEvent;

/**
 * Mengonfirmasi impor secara mengalir, menyediakan pembaruan progres langsung.
 *
 * @param file Berkas TXT, Markdown, atau ZIP
 * @param title Judul buku
 * @param description Deskripsi (opsional)
 * @param cover Berkas sampul (opsional)
 * @param splitMode Mode pemisahan
 * @param chunkSize Jumlah kata per bab saat pemisahan manual
 * @param onEvent Callback peristiwa
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

    // Mengurai peristiwa SSE
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
            console.warn("Tidak dapat mengurai peristiwa SSE:", line);
          } else {
            throw e;
          }
        }
      }
    }
  }

  return result;
}
