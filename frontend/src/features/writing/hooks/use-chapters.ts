/**
 * Chapter Hooks
 *
 * 章节数据操作的 React Query hooks。
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  fetchChapter,
  createChapter,
  updateChapter,
  deleteChapter,
  reorderChapters,
  moveChapterToVolume,
} from "@/lib/api-client";
import type { ChapterCreate, ChapterUpdate } from "@/lib/chapter.types";

/**
 * 获取单个章节（完整内容）
 *
 * 缓存策略：
 * - staleTime: 2分钟内数据视为新鲜，不会重新请求
 * - gcTime: 10分钟后才清理缓存，切换标签页时可复用
 */
export function useChapter(chapterId: string | null) {
  return useQuery({
    queryKey: ["chapter", chapterId],
    queryFn: () => fetchChapter(chapterId!),
    enabled: !!chapterId,
    staleTime: 2 * 60 * 1000, // 2分钟内缓存有效
    gcTime: 10 * 60 * 1000, // 10分钟后清理
  });
}

/**
 * 创建章节
 */
export function useCreateChapter(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ChapterCreate) => createChapter(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["volume-tree", projectId] });
      queryClient.invalidateQueries({ queryKey: ["chapter-summary-list", projectId] });
      queryClient.invalidateQueries({ queryKey: ["long-term-summaries-page", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

/**
 * 更新章节
 */
export function useUpdateChapter() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ chapterId, data }: { chapterId: string; data: ChapterUpdate }) =>
      updateChapter(chapterId, data),
    onSuccess: (updatedChapter) => {
      queryClient.setQueryData(["chapter", updatedChapter.id], updatedChapter);
      queryClient.invalidateQueries({
        queryKey: ["volume-tree", updatedChapter.projectId],
      });
      queryClient.invalidateQueries({
        queryKey: ["chapter-summary-list", updatedChapter.projectId],
      });
      queryClient.invalidateQueries({
        queryKey: ["long-term-summaries-page", updatedChapter.projectId],
      });
      // 刷新项目信息（更新 word_count）
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

/**
 * 删除章节
 */
export function useDeleteChapter(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (chapterId: string) => deleteChapter(chapterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["volume-tree", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

/**
 * 批量重排章节顺序
 */
export function useReorderChapters(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ volumeId, chapterIds }: { volumeId: string; chapterIds: string[] }) =>
      reorderChapters(volumeId, chapterIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["volume-tree", projectId] });
    },
  });
}

export function useMoveChapterToVolume(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ chapterId, volumeId }: { chapterId: string; volumeId: string }) =>
      moveChapterToVolume(chapterId, { volumeId }),
    onSuccess: (chapter) => {
      queryClient.invalidateQueries({ queryKey: ["volume-tree", projectId] });
      queryClient.invalidateQueries({ queryKey: ["chapter", chapter.id] });
    },
  });
}
