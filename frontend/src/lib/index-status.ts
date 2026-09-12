/**
 * Index Status - tipe status indeks, API, dan hooks.
 *
 * Dipakai bersama oleh indikator status pada bilah sisi Agent dan informasi indeks di halaman pengaturan.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo } from "react";

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

export const OVERALL_INDEX_STATUS_QUERY_KEY = [INDEX_STATUS_QUERY_KEY_PREFIX, "overall"] as const;

export async function fetchProjectIndexStatus(projectId: string): Promise<ProjectIndexStatus> {
  const response = await apiClient.get<ProjectIndexStatus>(
    `/projects/${projectId}/retrieval/index/status`,
  );
  return response.data;
}

export async function fetchOverallIndexStatus(): Promise<OverallIndexStatus> {
  const response = await apiClient.get<OverallIndexStatus>(`/retrieval/index/status`);
  return response.data;
}

export async function startProjectIndex(projectId: string): Promise<void> {
  await apiClient.post(`/projects/${projectId}/retrieval/index/start`);
}

export async function stopProjectIndex(projectId: string): Promise<void> {
  await apiClient.post(`/projects/${projectId}/retrieval/index/stop`);
}

/** Warna tampilan untuk setiap status indeks (variabel warna Radix). */
export function getIndexStatusColor(status: IndexStatus | null | undefined): string {
  if (status === "fresh") return "var(--green-9)";
  if (status === "indexing") return "var(--blue-9)";
  if (status === "failed") return "var(--red-9)";
  if (status === "stale" || status === "no_index" || status === "not_configured")
    return "var(--amber-9)";
  if (status === "needs_rebuild") return "var(--red-9)";
  return "var(--gray-9)";
}

/**
 * Berlangganan status indeks satu proyek: nilai awal diambil lewat API, pembaruan berikutnya dikirim lewat socket.
 */
export function useProjectIndexStatus(projectId: string, enabled = true) {
  const queryClient = useQueryClient();
  const queryKey = useMemo(() => getProjectIndexStatusQueryKey(projectId), [projectId]);

  const query = useQuery({
    queryKey,
    queryFn: () => fetchProjectIndexStatus(projectId),
    enabled: enabled && Boolean(projectId),
    // Tanpa penjajakan berkala: nilai awal diambil lewat API, pembaruan berikutnya dikirim lewat socket index:status.
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
      },
    );
    return () => sub.close();
  }, [projectId, enabled, queryClient, queryKey]);

  return query;
}

/**
 * Berlangganan status indeks keseluruhan (informasi indeks halaman pengaturan): nilai awal diambil lewat API, pembaruan berikutnya dikirim lewat socket.
 *
 * - index:config (siaran): konfigurasi indeks global berubah, disegarkan menyeluruh.
 * - index:status (per ruang proyek): status satu proyek berubah, digabungkan secara bertahap ke singgahan overall lalu rekapnya dihitung ulang.
 */
export function useOverallIndexStatus(enabled = true) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: OVERALL_INDEX_STATUS_QUERY_KEY,
    queryFn: fetchOverallIndexStatus,
    enabled,
    // Tanpa penjajakan berkala: nilai awal diambil lewat API, pembaruan berikutnya bertahap lewat peristiwa socket.
  });

  // Menggabungkan index:status satu proyek secara bertahap ke singgahan overall, lalu menghitung ulang field rekap.
  const mergeProjectStatus = useCallback(
    (status: ProjectIndexStatus) => {
      queryClient.setQueryData<OverallIndexStatus>(OVERALL_INDEX_STATUS_QUERY_KEY, (prev) => {
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
      });
    },
    [queryClient],
  );

  // Siaran index:config: konfigurasi menyeluruh berubah (misalnya jangkauan aktif/pergantian model), status dan pengaturan keseluruhan disegarkan.
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

  // Berlangganan kiriman index:status setiap proyek yang aktif, digabungkan secara bertahap ke singgahan overall.
  const projectIds = useMemo(
    () => query.data?.projects.map((p) => p.project_id) ?? [],
    [query.data?.projects],
  );
  const projectIdsKey = projectIds.join("|");
  useEffect(() => {
    if (!enabled || projectIds.length === 0) return;
    const subs = projectIds.map((pid) =>
      subscribeIndexStatus(pid, (raw) => {
        if (raw && typeof raw.project_id === "string") {
          mergeProjectStatus(raw as unknown as ProjectIndexStatus);
        }
      }),
    );
    return () => subs.forEach((s) => s.close());
    // projectIdsKey sebagai dependensi: langganan dibuat ulang saat daftar proyek berubah.
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

export function useStopProjectIndex(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => stopProjectIndex(projectId),
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
