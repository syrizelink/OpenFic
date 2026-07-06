/**
 * Index Status — 索引状态类型、API 与 hooks。
 *
 * 供 Agent 侧边栏状态指示器与设置页索引信息共用。
 */

import { useCallback, useEffect, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import { subscribeIndexStatus } from "@/lib/background-socket";

export type IndexStatus =
  | "disabled"
  | "not_configured"
  | "no_chapters"
  | "no_index"
  | "indexing"
  | "needs_rebuild"
  | "stale"
  | "fresh"
  | "failed";

export type IndexMode = "off" | "all" | "selected";
export type IndexAutoStrategy = "immediate" | "agent_decided" | "off";

export interface ProjectIndexStatus {
  project_id: string;
  enabled: boolean;
  status: IndexStatus;
  title: string;
  total_chapters: number;
  indexed_count: number;
  pending_count: number;
  in_progress_count: number;
  failed_count: number;
  empty_content_count: number;
  last_error: string | null;
  progress: number;
}

export interface OverallIndexStatus {
  mode: IndexMode;
  embedding_model_configured: boolean;
  total_projects: number;
  total_chapters: number;
  indexed_count: number;
  pending_count: number;
  in_progress_count: number;
  failed_count: number;
  projects: ProjectIndexStatus[];
}

export const INDEX_STATUS_QUERY_KEY_PREFIX = "index-status";

export function getProjectIndexStatusQueryKey(projectId: string) {
  return [INDEX_STATUS_QUERY_KEY_PREFIX, "project", projectId] as const;
}

export const OVERALL_INDEX_STATUS_QUERY_KEY = [
  INDEX_STATUS_QUERY_KEY_PREFIX,
  "overall",
] as const;

export async function fetchProjectIndexStatus(
  projectId: string
): Promise<ProjectIndexStatus> {
  const response = await apiClient.get<ProjectIndexStatus>(
    `/projects/${projectId}/retrieval/index/status`
  );
  return response.data;
}

export async function fetchOverallIndexStatus(): Promise<OverallIndexStatus> {
  const response = await apiClient.get<OverallIndexStatus>(
    `/retrieval/index/status`
  );
  return response.data;
}

export async function startProjectIndex(projectId: string): Promise<void> {
  await apiClient.post(`/projects/${projectId}/retrieval/index/start`);
}

/** 索引状态对应的展示颜色（Radix 颜色变量）。 */
export function getIndexStatusColor(
  status: IndexStatus | null | undefined
): string {
  if (status === "fresh") return "var(--green-9)";
  if (status === "indexing") return "var(--blue-9)";
  if (status === "failed") return "var(--red-9)";
  if (status === "stale" || status === "no_index" || status === "not_configured")
    return "var(--amber-9)";
  if (status === "needs_rebuild") return "var(--red-9)";
  return "var(--gray-9)";
}

/**
 * 订阅单个项目的索引状态：初始由 API 获取，后续由 socket 推送更新。
 */
export function useProjectIndexStatus(projectId: string, enabled = true) {
  const queryClient = useQueryClient();
  const queryKey = useMemo(
    () => getProjectIndexStatusQueryKey(projectId),
    [projectId]
  );

  const query = useQuery({
    queryKey,
    queryFn: () => fetchProjectIndexStatus(projectId),
    enabled: enabled && Boolean(projectId),
    // 不轮询：初始由 API 获取，后续由 socket index:status 推送更新。
  });

  useEffect(() => {
    if (!enabled || !projectId) return;
    const sub = subscribeIndexStatus(
      projectId,
      (status) => {
        if (status?.project_id === projectId) {
          queryClient.setQueryData(queryKey, status);
        }
      },
      () => {
        void queryClient.invalidateQueries({ queryKey });
      }
    );
    return () => sub.close();
  }, [projectId, enabled, queryClient, queryKey]);

  return query;
}

/**
 * 订阅总体索引状态（设置页索引信息）：初始由 API 获取，后续由 socket 推送更新。
 *
 * - index:config（广播）：全局索引配置变更，整体刷新。
 * - index:status（按项目房间）：单个项目状态变更，增量合并进 overall 缓存并重算汇总。
 */
export function useOverallIndexStatus(enabled = true) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: OVERALL_INDEX_STATUS_QUERY_KEY,
    queryFn: fetchOverallIndexStatus,
    enabled,
    // 不轮询：初始由 API 获取，后续由 socket 事件增量更新。
  });

  // 将单个项目的 index:status 增量合并进 overall 缓存，并重算汇总字段。
  const mergeProjectStatus = useCallback(
    (status: ProjectIndexStatus) => {
      queryClient.setQueryData<OverallIndexStatus>(
        OVERALL_INDEX_STATUS_QUERY_KEY,
        (prev) => {
          if (!prev) return prev;
          let found = false;
          const projects = prev.projects.map((p) => {
            if (p.project_id === status.project_id) {
              found = true;
              return status;
            }
            return p;
          });
          if (!found) {
            projects.push(status);
          }
          const sum = (sel: (p: ProjectIndexStatus) => number) =>
            projects.reduce((acc, p) => acc + sel(p), 0);
          return {
            ...prev,
            projects,
            total_projects: projects.length,
            total_chapters: sum((p) => p.total_chapters),
            indexed_count: sum((p) => p.indexed_count),
            pending_count: sum((p) => p.pending_count),
            in_progress_count: sum((p) => p.in_progress_count),
            failed_count: sum((p) => p.failed_count),
          };
        }
      );
    },
    [queryClient]
  );

  // index:config 广播：整体配置变更（如启用范围/模型切换），刷新整体状态与设置。
  useEffect(() => {
    if (!enabled) return;
    const configSub = subscribeIndexStatus("__global__", undefined, () => {
      void queryClient.invalidateQueries({
        queryKey: OVERALL_INDEX_STATUS_QUERY_KEY,
      });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    });
    return () => configSub.close();
  }, [enabled, queryClient]);

  // 订阅每个启用项目的 index:status 推送，增量合并进 overall 缓存。
  const projectIds = useMemo(
    () => query.data?.projects.map((p) => p.project_id) ?? [],
    [query.data?.projects]
  );
  const projectIdsKey = projectIds.join("|");
  useEffect(() => {
    if (!enabled || projectIds.length === 0) return;
    const subs = projectIds.map((pid) =>
      subscribeIndexStatus(pid, (raw) => {
        if (raw && typeof raw.project_id === "string") {
          mergeProjectStatus(raw as unknown as ProjectIndexStatus);
        }
      })
    );
    return () => subs.forEach((s) => s.close());
    // projectIdsKey 作为依赖：项目列表变化时重新订阅。
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, projectIdsKey, mergeProjectStatus]);

  return query;
}

export function useStartProjectIndex(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => startProjectIndex(projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: getProjectIndexStatusQueryKey(projectId),
      });
      void queryClient.invalidateQueries({
        queryKey: OVERALL_INDEX_STATUS_QUERY_KEY,
      });
    },
  });
}
