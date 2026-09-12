/**
 * Chapter Hooks
 *
 * Hooks React Query untuk operasi data bab.
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
 * Mengambil satu bab (isi lengkap)
 *
 * Strategi singgahan:
 * - staleTime: data dianggap segar selama 2 menit, tidak diminta ulang
 * - gcTime: singgahan baru dibersihkan setelah 10 menit, bisa dipakai ulang saat berpindah tab
 */
export function useChapter(chapterId: string | null) {
  return useQuery({
    queryKey: ["chapter", chapterId],
    queryFn: () => fetchChapter(chapterId!),
    enabled: !!chapterId,
    staleTime: 2 * 60 * 1000, // Singgahan berlaku selama 2 menit
    gcTime: 10 * 60 * 1000, // Dibersihkan setelah 10 menit
  });
}

/**
 * Membuat bab
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
 * Memperbarui bab
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
      // Menyegarkan informasi proyek (memperbarui word_count)
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

/**
 * Menghapus bab
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
 * Mengurutkan ulang bab secara massal
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
