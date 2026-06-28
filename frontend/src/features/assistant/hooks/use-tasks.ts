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
      toast.error(`更新任务失败：${error.message}`);
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
      toast.success("任务已删除");
    },
    onError: (error: Error) => {
      toast.error(`删除任务失败：${error.message}`);
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
          ? `已删除 ${result.deletedCount} 个任务，跳过 ${result.skippedRunningCount} 个运行中的任务`
          : `已删除 ${result.deletedCount} 个任务`
      );
    },
    onError: (error: Error) => {
      toast.error(`批量删除任务失败：${error.message}`);
    },
  });
}
