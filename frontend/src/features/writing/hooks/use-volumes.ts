import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createVolume,
  deleteVolume,
  fetchChapters,
  fetchProject,
  moveVolume,
  updateVolume,
} from "@/lib/api-client";
import type { VolumeCreate, VolumeUpdate } from "@/lib/chapter.types";
import type { ProjectListResponse } from "@/lib/project.types";

import { projectsQueryKey } from "../../projects/hooks/use-projects";
import {
  importDocumentsIntoProject,
  type DocumentImportOptions,
  type DocumentImportPlacement,
} from "../../projects/lib/import-api";

async function syncImportedProjectListItem(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string,
): Promise<void> {
  try {
    const project = await fetchProject(projectId);
    const cachedProjectLists = queryClient.getQueriesData<ProjectListResponse>({
      queryKey: projectsQueryKey,
    });

    await Promise.all(
      cachedProjectLists
        .filter(([, current]) => current?.items.some((item) => item.id === projectId))
        .map(async ([queryKey]) => {
          queryClient.setQueryData<ProjectListResponse>(queryKey, (current) => {
            if (!current) return current;
            return {
              ...current,
              items: current.items.map((item) => (item.id === projectId ? project : item)),
            };
          });
          await queryClient.invalidateQueries({ queryKey, exact: true, refetchType: "none" });
        }),
    );
  } catch {
    // Import already succeeded; cache synchronization is deliberately best-effort.
  }
}

export function useVolumeTree(projectId: string) {
  return useQuery({
    queryKey: ["volume-tree", projectId],
    queryFn: () => fetchChapters(projectId),
    enabled: !!projectId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateVolume(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: VolumeCreate) => createVolume(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["volume-tree", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useUpdateVolume() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ volumeId, data }: { volumeId: string; data: VolumeUpdate }) =>
      updateVolume(volumeId, data),
    onSuccess: (volume) => {
      queryClient.invalidateQueries({ queryKey: ["volume-tree", volume.projectId] });
    },
  });
}

export function useDeleteVolume(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ volumeId, cascade = false }: { volumeId: string; cascade?: boolean }) =>
      deleteVolume(volumeId, cascade),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["volume-tree", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useMoveVolume(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ volumeId, newOrder }: { volumeId: string; newOrder: number }) =>
      moveVolume(volumeId, { newOrder }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["volume-tree", projectId] });
    },
  });
}

/** Import parsed documents into this project and refresh only its affected views. */
export function useImportDocumentsIntoProject(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      files,
      placement,
      options,
    }: {
      files: File[];
      placement: DocumentImportPlacement;
      options: DocumentImportOptions;
    }) => importDocumentsIntoProject(projectId, files, placement, options),
    onSuccess: () => {
      void syncImportedProjectListItem(queryClient, projectId);
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["volume-tree", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["project", projectId] }),
      ]).catch(() => undefined);
    },
  });
}
