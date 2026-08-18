/**
 * Projects Query Hooks
 *
 * 使用 TanStack Query 管理项目数据的异步状态。
 */

import { keepPreviousData, useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { fetchProjects, createProject, updateProject, deleteProject } from "@/lib/api-client";
import { deleteAgentInputHistory, removeRecentProjectByProjectId } from "@/lib/local-db";
import type { ProjectCreate, ProjectUpdate, ProjectListParams } from "@/lib/project.types";
import type { RecentProject } from "@/lib/recent-projects";

/** 项目列表查询 key */
export const projectsQueryKey = ["projects"] as const;

/**
 * 获取项目列表
 */
export function useProjects(params?: ProjectListParams) {
  return useQuery({
    queryKey: [...projectsQueryKey, params],
    queryFn: () => fetchProjects(params),
    placeholderData: keepPreviousData,
  });
}

/**
 * 创建项目
 */
export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProjectCreate) => createProject(data),
    onSuccess: async () => {
      await queryClient.refetchQueries({ queryKey: projectsQueryKey });
    },
  });
}

/**
 * 更新项目
 */
export function useUpdateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, data }: { projectId: string; data: ProjectUpdate }) =>
      updateProject(projectId, data),
    onSuccess: async () => {
      await queryClient.refetchQueries({ queryKey: projectsQueryKey });
    },
  });
}

/**
 * 删除项目
 */
export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (projectId: string) => deleteProject(projectId),
    onSuccess: async (_data, projectId) => {
      await queryClient.cancelQueries({ queryKey: ["recent-projects"] });
      await Promise.all([
        removeRecentProjectByProjectId(projectId),
        deleteAgentInputHistory(projectId),
      ]);
      queryClient.setQueryData<RecentProject[]>(["recent-projects"], (recentProjects) =>
        recentProjects?.filter((project) => project.projectId !== projectId),
      );
      queryClient.removeQueries({ queryKey: ["project", projectId] });
      await queryClient.refetchQueries({ queryKey: projectsQueryKey });
    },
  });
}
