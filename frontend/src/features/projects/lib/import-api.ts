/**
 * 导入 API - TXT 文件导入相关接口。
 */

import axios from "axios";

const API_BASE = "/api/v1";

/** 预览章节信息 */
export interface PreviewChapter {
  title: string;
  word_count: number;
  content_preview: string;
}

/** 导入预览响应 */
export interface ImportPreviewResponse {
  chapters: PreviewChapter[];
  total_word_count: number;
  chapter_count: number;
  detected_encoding: string;
}

/** 确认导入响应 */
export interface ImportConfirmResponse {
  project_id: string;
  title: string;
  chapter_count: number;
  total_word_count: number;
}

/**
 * 预览 TXT 文件解析结果。
 *
 * @param file TXT 文件
 * @returns 解析预览结果
 */
export async function previewTxtFile(
  file: File
): Promise<ImportPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await axios.post<ImportPreviewResponse>(
    `${API_BASE}/import/preview`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );

  return response.data;
}

/**
 * 确认导入，创建项目和章节。
 *
 * @param file TXT 文件
 * @param title 书名
 * @param description 简介（可选）
 * @param cover 封面文件（可选）
 * @returns 导入结果
 */
export async function confirmImport(
  file: File,
  title: string,
  description?: string,
  cover?: File | null
): Promise<ImportConfirmResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);

  if (description) {
    formData.append("description", description);
  }

  if (cover) {
    formData.append("cover", cover);
  }

  const response = await axios.post<ImportConfirmResponse>(
    `${API_BASE}/import/confirm`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );

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
export type ImportEvent =
  | ImportProgressEvent
  | ImportCompleteEvent
  | ImportErrorEvent;

/**
 * 流式确认导入，提供实时进度更新。
 *
 * @param file TXT 文件
 * @param title 书名
 * @param description 简介（可选）
 * @param cover 封面文件（可选）
 * @param onEvent 事件回调
 */
export async function confirmImportStream(
  file: File,
  title: string,
  description: string | undefined,
  cover: File | null | undefined,
  onEvent: (event: ImportEvent) => void
): Promise<ImportConfirmResponse | null> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);

  if (description) {
    formData.append("description", description);
  }

  if (cover) {
    formData.append("cover", cover);
  }

  const response = await fetch(`${API_BASE}/import/confirm-stream`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("无法获取响应流");
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
