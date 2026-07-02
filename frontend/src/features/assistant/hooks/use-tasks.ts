/**
 * Tasks Hooks
 *
 * 任务相关的 React Query hooks。
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTask,
  fetchTasks,
  updateTask,
  deleteTask,
  deleteAllTasks,
} from "@/lib/api-client";
import i18n from "@/i18n";
import type {
  Task,
  TaskListResponse,
  UpdateTaskRequest,
} from "@/lib/task.types";
import { toast } from "@/components";

function getTasksQueryKey(
  projectId: string,
  params?: {
    limit?: number;
    offset?: number;
    search?: string;
    favorited?: boolean;
  }
) {
  return ["tasks", projectId, params] as const;
}

/**
 * 获取任务列表
 */
export function useTasks(
  projectId: string,
  params?: {
    limit?: number;
    offset?: number;
    search?: string;
    favorited?: boolean;
  }
) {
  return useQuery<TaskListResponse>({
    queryKey: getTasksQueryKey(projectId, params),
    queryFn: () => fetchTasks(projectId, params),
    enabled: !!projectId,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

/**
 * 获取任务详情
 */
export function useTask(taskId: string | null) {
  return useQuery<Task>({
    queryKey: ["task", taskId],
    queryFn: () => fetchTask(taskId!),
    enabled: !!taskId,
  });
}

/**
 * 更新任务
 */
export function useUpdateTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ taskId, data }: { taskId: string; data: UpdateTaskRequest }) =>
      updateTask(taskId, data),
    onSuccess: (updatedTask) => {
      queryClient.setQueryData(["task", updatedTask.id], updatedTask);
      queryClient.invalidateQueries({
        queryKey: ["tasks", updatedTask.projectId],
        exact: false,
      });
    },
    onError: (error: Error) => {
      toast.error(i18n.t("writing.aiSidebar.updateTaskFailed", { error: error.message }));
    },
  });
}

/**
 * 删除任务
 */
export function useDeleteTask(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (taskId: string) => deleteTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["tasks", projectId],
        exact: false,
      });
      toast.success(i18n.t("writing.aiSidebar.taskDeletedToast"));
    },
    onError: (error: Error) => {
      toast.error(i18n.t("writing.aiSidebar.deleteTaskFailed", { error: error.message }));
    },
  });
}

export function useDeleteAllTasks(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => deleteAllTasks(projectId),
    onSuccess: (result) => {
      queryClient.invalidateQueries({
        queryKey: ["tasks", projectId],
        exact: false,
      });
      toast.success(
        result.skippedRunningCount > 0
          ? i18n.t("writing.aiSidebar.deleteAllTasksResultWithRunning", { deleted: result.deletedCount, skipped: result.skippedRunningCount })
          : i18n.t("writing.aiSidebar.deleteAllTasksResult", { deleted: result.deletedCount })
      );
    },
    onError: (error: Error) => {
      toast.error(i18n.t("writing.aiSidebar.batchDeleteFailed", { error: error.message }));
    },
  });
}
