import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { useEffect } from "react";

import {
  deleteChapterSummaries,
  deleteLongTermSummaries,
  enqueueSummary,
  fetchChapterSummaryList,
  fetchLongTermSummariesPage,
  subscribeBackgroundProjection,
  transformSummaryRealtimeSnapshot,
  type BackgroundEvent,
  type BackgroundProjectionSubscription,
  type BackgroundSnapshot,
  type ChapterSummaryListResponse,
  type EnqueueSummaryRequest,
  type LongTermSummaryListResponse,
  type SummaryBackgroundJobItem,
  type SummaryMaintenance,
  type SummaryPanelResponse,
  type SummaryStatus,
  type SummaryStatusItem,
} from "@/lib/api-client";

import {
  extractBatchProgressFromEvent,
  ITEM_TERMINAL_EVENT_TYPES,
  updateBatchProgressForItemEvent,
} from "../lib/summary-batch-progress";

const SUMMARY_PAGE_SIZE = 20;
const SUMMARY_PROJECTION_QUERY_KEY = "summary-projection";

const SUMMARY_JOB_TYPES = new Set(["chapter_summary", "long_term_summary", "summary_batch"]);
const SUMMARY_ITEM_TYPES = new Set(["chapter_summary", "long_term_summary"]);
const SUMMARY_EVENT_TYPES = new Set([
  "background_job_started",
  "background_job_progress",
  "background_job_succeeded",
  "background_job_failed",
  "background_job_skipped",
  "background_item_queued",
  "background_item_progress",
  "background_item_succeeded",
  "background_item_failed",
  "background_item_skipped",
  "chapter_summary_updated",
  "long_term_summary_updated",
]);
interface SummaryProjection {
  projectId: string;
  projectRevision: number | null;
  statuses: SummaryStatusItem[];
  maintenance: SummaryMaintenance;
}

const summaryProjectionSubscriptions = new Map<
  string,
  { count: number; subscription: BackgroundProjectionSubscription }
>();

function getSummaryProjectionQueryKey(projectId: string) {
  return [SUMMARY_PROJECTION_QUERY_KEY, projectId] as const;
}

function isSummaryBackgroundEvent(event: BackgroundEvent): boolean {
  if (!SUMMARY_EVENT_TYPES.has(event.type)) return false;
  if (event.type === "chapter_summary_updated" || event.type === "long_term_summary_updated") {
    return true;
  }
  if (typeof event.job_type === "string" && SUMMARY_JOB_TYPES.has(event.job_type)) {
    return true;
  }
  if (typeof event.item_type === "string" && SUMMARY_ITEM_TYPES.has(event.item_type)) {
    return true;
  }
  return false;
}

function createEmptySummaryMaintenance(): SummaryMaintenance {
  return {
    autoGenerationBlocked: false,
    blockReason: null,
    missingOrFailedChapterSummaries: [],
    missingOrFailedLongTermSummaries: [],
    skippedChapterSummaries: [],
    batchProgress: null,
    activeJobs: [],
  };
}

function createEmptySummaryProjection(projectId: string): SummaryProjection {
  return {
    projectId,
    projectRevision: null,
    statuses: [],
    maintenance: createEmptySummaryMaintenance(),
  };
}

function getProjection(queryClient: QueryClient, projectId: string): SummaryProjection {
  return (
    queryClient.getQueryData<SummaryProjection>(getSummaryProjectionQueryKey(projectId)) ??
    createEmptySummaryProjection(projectId)
  );
}

function normalizeRevision(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function shouldApplyEventRevision(
  currentRevision: number | null,
  eventRevision: number | null,
): boolean {
  if (eventRevision == null) return true;
  if (currentRevision == null) return true;
  return eventRevision > currentRevision;
}

function shouldApplySnapshotRevision(
  currentRevision: number | null,
  snapshotRevision: number | null,
): boolean {
  if (snapshotRevision == null) return true;
  if (currentRevision == null) return true;
  return snapshotRevision >= currentRevision;
}

function getString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function getNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function normalizeSummaryStatus(value: unknown): SummaryStatus | null {
  if (
    value === "not_generated" ||
    value === "queued" ||
    value === "running" ||
    value === "ready" ||
    value === "failed"
  ) {
    return value;
  }
  if (value === "succeeded") return "ready";
  if (value === "failed") return "failed";
  return null;
}

function resolveSummaryId(payload: Record<string, unknown>, current: string | null): string | null {
  if (!("summary_id" in payload)) return current;
  return getString(payload.summary_id);
}

function resolveUpdatedAt(payload: Record<string, unknown>, current: string | null): string | null {
  if (!("updated_at" in payload)) return current;
  return getString(payload.updated_at);
}

function resolveProgressMessage(
  payload: Record<string, unknown>,
  current: string | null,
): string | null {
  if ("progress_message" in payload) return getString(payload.progress_message);
  if ("message" in payload) return getString(payload.message);
  return current;
}

function applyChapterStatusToProjection(
  projection: SummaryProjection,
  payload: Record<string, unknown>,
): SummaryProjection {
  const chapterId = getString(payload.chapter_id);
  const status = normalizeSummaryStatus(payload.status);
  if (!chapterId || !status) return projection;

  const isStale = getBoolean(payload.is_stale);
  const progressMessage = status === "ready" ? null : resolveProgressMessage(payload, null);
  let statusFound = false;
  const statuses = projection.statuses.map((item) => {
    if (item.chapterId !== chapterId) return item;
    statusFound = true;
    return {
      ...item,
      status,
      isStale,
      summaryId: resolveSummaryId(payload, item.summaryId),
      updatedAt: resolveUpdatedAt(payload, item.updatedAt),
    };
  });
  if (!statusFound) {
    statuses.push({
      chapterId,
      volumeId: null,
      status,
      isStale,
      summaryId: resolveSummaryId(payload, null),
      updatedAt: resolveUpdatedAt(payload, null),
    });
  }

  let missingFound = false;
  const missingOrFailedChapterSummaries = projection.maintenance.missingOrFailedChapterSummaries
    .map((item) => {
      if (item.chapterId !== chapterId) return item;
      missingFound = true;
      return {
        ...item,
        status,
        isStale,
        summaryId: resolveSummaryId(payload, item.summaryId),
        progressMessage:
          status === "ready" ? null : resolveProgressMessage(payload, item.progressMessage),
      };
    })
    .filter((item) => !(item.chapterId === chapterId && item.status === "ready" && !item.isStale));

  const chapterOrder = getNumber(payload.chapter_order);
  if (!missingFound && !(status === "ready" && !isStale) && chapterOrder != null) {
    missingOrFailedChapterSummaries.push({
      chapterId,
      chapterOrder,
      volumeId: null,
      volumeTitle: null,
      volumeOrder: null,
      chapterTitle: getString(payload.chapter_title) ?? chapterId,
      status,
      isStale,
      summaryId: resolveSummaryId(payload, null),
      progressMessage,
    });
  }

  return {
    ...projection,
    statuses,
    maintenance: {
      ...projection.maintenance,
      missingOrFailedChapterSummaries,
    },
  };
}

function applyLongTermStatusToProjection(
  projection: SummaryProjection,
  payload: Record<string, unknown>,
): SummaryProjection {
  const startOrder = getNumber(payload.start_order);
  const endOrder = getNumber(payload.end_order);
  const status = normalizeSummaryStatus(payload.status);
  if (startOrder == null || endOrder == null || !status) return projection;

  const isStale = getBoolean(payload.is_stale);
  let found = false;
  const missingOrFailedLongTermSummaries = projection.maintenance.missingOrFailedLongTermSummaries
    .map((item) => {
      if (item.startOrder !== startOrder || item.endOrder !== endOrder) return item;
      found = true;
      return {
        ...item,
        status,
        isStale,
        summaryId: resolveSummaryId(payload, item.summaryId),
        progressMessage:
          status === "ready" ? null : resolveProgressMessage(payload, item.progressMessage),
      };
    })
    .filter(
      (item) =>
        !(
          item.startOrder === startOrder &&
          item.endOrder === endOrder &&
          item.status === "ready" &&
          !item.isStale
        ),
    );

  if (!found && !(status === "ready" && !isStale)) {
    missingOrFailedLongTermSummaries.push({
      startOrder,
      endOrder,
      status,
      isStale,
      summaryId: resolveSummaryId(payload, null),
      progressMessage: status === "ready" ? null : resolveProgressMessage(payload, null),
    });
  }

  return {
    ...projection,
    maintenance: {
      ...projection.maintenance,
      missingOrFailedLongTermSummaries,
    },
  };
}

function buildActiveJobFromEvent(
  event: BackgroundEvent,
  existing: SummaryBackgroundJobItem | undefined,
): SummaryBackgroundJobItem | null {
  const jobId = getString(event.item_id) ?? getString(event.job_id);
  const payload = event.payload ?? {};
  const jobType =
    event.item_type === "chapter_summary" || event.item_type === "long_term_summary"
      ? event.item_type
      : event.job_type === "chapter_summary" ||
          event.job_type === "long_term_summary" ||
          event.job_type === "summary_batch"
        ? event.job_type
        : null;
  if (!jobId || !jobType) return null;

  const now = event.created_at ?? new Date().toISOString();
  return {
    jobId,
    jobType,
    status: event.type === "background_item_queued" ? "pending" : "running",
    chapterId: getString(payload.chapter_id) ?? existing?.chapterId ?? null,
    summaryId: resolveSummaryId(payload, existing?.summaryId ?? null),
    startOrder: getNumber(payload.start_order) ?? existing?.startOrder ?? null,
    endOrder: getNumber(payload.end_order) ?? existing?.endOrder ?? null,
    progressCurrent:
      getNumber(payload.progress_current) ??
      getNumber(payload.current) ??
      existing?.progressCurrent ??
      0,
    progressTotal:
      "progress_total" in payload
        ? getNumber(payload.progress_total)
        : (getNumber(payload.total) ?? existing?.progressTotal ?? null),
    progressMessage: resolveProgressMessage(payload, existing?.progressMessage ?? null),
    errorMessage:
      "error_message" in payload
        ? getString(payload.error_message)
        : (existing?.errorMessage ?? null),
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  };
}

function applyItemEventToProjection(
  projection: SummaryProjection,
  event: BackgroundEvent,
): SummaryProjection {
  const jobId = getString(event.item_id) ?? getString(event.job_id);
  const payload = event.payload ?? {};
  let next = projection;

  if (event.item_type === "chapter_summary") {
    next = applyChapterStatusToProjection(next, payload);
  } else if (event.item_type === "long_term_summary") {
    next = applyLongTermStatusToProjection(next, payload);
  }

  const previousJob = jobId
    ? next.maintenance.activeJobs.find((job) => job.jobId === jobId)
    : undefined;
  const activeJobs = ITEM_TERMINAL_EVENT_TYPES.has(event.type)
    ? next.maintenance.activeJobs.filter((job) => job.jobId !== jobId)
    : (() => {
        const nextJob = buildActiveJobFromEvent(event, previousJob);
        if (!nextJob) return next.maintenance.activeJobs;
        return [
          ...next.maintenance.activeJobs.filter((job) => job.jobId !== nextJob.jobId),
          nextJob,
        ];
      })();

  return {
    ...next,
    maintenance: {
      ...next.maintenance,
      activeJobs,
      batchProgress: updateBatchProgressForItemEvent(
        next.maintenance.batchProgress,
        event,
        previousJob,
      ),
    },
  };
}

function applyJobEventToProjection(
  projection: SummaryProjection,
  event: BackgroundEvent,
): SummaryProjection {
  const jobId = getString(event.job_id);
  const itemId = getString(event.item_id);
  if (!jobId && !itemId) return projection;

  if (event.type === "background_job_started" || event.type === "background_job_progress") {
    const batchProgress =
      event.type === "background_job_progress"
        ? extractBatchProgressFromEvent(event, projection.maintenance.batchProgress)
        : projection.maintenance.batchProgress?.jobId === jobId
          ? {
              ...projection.maintenance.batchProgress,
              status: "running",
              updatedAt: event.created_at ?? projection.maintenance.batchProgress.updatedAt,
            }
          : projection.maintenance.batchProgress;

    return {
      ...projection,
      maintenance: {
        ...projection.maintenance,
        batchProgress,
        activeJobs: projection.maintenance.activeJobs.map((job) =>
          (itemId != null ? job.jobId === itemId : job.jobId === jobId)
            ? {
                ...job,
                status: event.type === "background_job_started" ? "running" : job.status,
                progressCurrent:
                  getNumber(event.payload?.current) ??
                  getNumber(event.payload?.progress_current) ??
                  job.progressCurrent,
                progressTotal:
                  getNumber(event.payload?.total) ??
                  getNumber(event.payload?.progress_total) ??
                  job.progressTotal,
                progressMessage:
                  getString(event.payload?.message) ??
                  getString(event.payload?.progress_message) ??
                  job.progressMessage,
                updatedAt: event.created_at ?? job.updatedAt,
              }
            : job,
        ),
      },
    };
  }

  if (
    event.type === "background_job_succeeded" ||
    event.type === "background_job_failed" ||
    event.type === "background_job_skipped"
  ) {
    const currentBatchProgress =
      jobId && projection.maintenance.batchProgress?.jobId === jobId
        ? projection.maintenance.batchProgress
        : null;
    const terminalStatus =
      event.type === "background_job_succeeded"
        ? "succeeded"
        : event.type === "background_job_failed"
          ? "failed"
          : "skipped";
    const batchProgress = currentBatchProgress
      ? {
          ...currentBatchProgress,
          status: terminalStatus,
          completedItemCount:
            event.type === "background_job_succeeded"
              ? Math.max(
                  currentBatchProgress.completedItemCount,
                  currentBatchProgress.totalItemCount,
                )
              : currentBatchProgress.completedItemCount,
          progressCurrent:
            event.type === "background_job_succeeded"
              ? (currentBatchProgress.progressTotal ?? currentBatchProgress.progressCurrent)
              : currentBatchProgress.progressCurrent,
          progressPercent:
            event.type === "background_job_succeeded" ? 100 : currentBatchProgress.progressPercent,
          progressMessage:
            getString(event.payload?.message) ??
            getString(event.payload?.progress_message) ??
            currentBatchProgress.progressMessage,
          queuedItemCount: 0,
          runningItemCount: 0,
          updatedAt: event.created_at ?? currentBatchProgress.updatedAt,
        }
      : projection.maintenance.batchProgress;

    return {
      ...projection,
      maintenance: {
        ...projection.maintenance,
        batchProgress,
        activeJobs: projection.maintenance.activeJobs.filter((job) =>
          itemId != null ? job.jobId !== itemId : job.jobId !== jobId,
        ),
      },
    };
  }

  return projection;
}

function reduceSummaryProjectionEvent(
  projection: SummaryProjection,
  event: BackgroundEvent,
): SummaryProjection {
  let next = projection;
  if (event.type === "chapter_summary_updated" && event.payload) {
    next = applyChapterStatusToProjection(next, event.payload);
  } else if (event.type === "long_term_summary_updated" && event.payload) {
    next = applyLongTermStatusToProjection(next, event.payload);
  } else if (event.type.startsWith("background_item_")) {
    next = applyItemEventToProjection(next, event);
  } else {
    next = applyJobEventToProjection(next, event);
  }

  const eventRevision = normalizeRevision(event.project_revision);
  return eventRevision == null ? next : { ...next, projectRevision: eventRevision };
}

function applyChapterStatusToListQueries(
  queryClient: QueryClient,
  projectId: string,
  payload: Record<string, unknown>,
) {
  const chapterId = getString(payload.chapter_id);
  const status = normalizeSummaryStatus(payload.status);
  if (!chapterId || !status) return;

  queryClient.setQueriesData(
    { queryKey: ["chapter-summary-list", projectId] },
    (current: ChapterSummaryListResponse | undefined) => {
      if (!current) return current;
      return {
        ...current,
        items: current.items.map((item) =>
          item.chapterId === chapterId
            ? {
                ...item,
                status,
                isStale: getBoolean(payload.is_stale),
                summaryId: resolveSummaryId(payload, item.summaryId),
                updatedAt: resolveUpdatedAt(payload, item.updatedAt),
              }
            : item,
        ),
      };
    },
  );
}

function applyLongTermStatusToListQueries(
  queryClient: QueryClient,
  projectId: string,
  payload: Record<string, unknown>,
) {
  const startOrder = getNumber(payload.start_order);
  const endOrder = getNumber(payload.end_order);
  const status = normalizeSummaryStatus(payload.status);
  if (startOrder == null || endOrder == null || !status) return;

  queryClient.setQueriesData(
    { queryKey: ["long-term-summaries-page", projectId] },
    (current: LongTermSummaryListResponse | undefined) => {
      if (!current) return current;
      return {
        ...current,
        items: current.items.map((item) =>
          item.startOrder === startOrder && item.endOrder === endOrder
            ? {
                ...item,
                status,
                isStale: getBoolean(payload.is_stale),
                summaryId: resolveSummaryId(payload, item.summaryId),
                updatedAt: resolveUpdatedAt(payload, item.updatedAt),
              }
            : item,
        ),
      };
    },
  );
}

function applySummaryEventToListQueries(
  queryClient: QueryClient,
  projectId: string,
  event: BackgroundEvent,
) {
  if (!event.payload) return;
  if (event.type === "chapter_summary_updated" || event.item_type === "chapter_summary") {
    applyChapterStatusToListQueries(queryClient, projectId, event.payload);
  }
  if (event.type === "long_term_summary_updated" || event.item_type === "long_term_summary") {
    applyLongTermStatusToListQueries(queryClient, projectId, event.payload);
  }
}

function applySummarySnapshot(
  queryClient: QueryClient,
  projectId: string,
  snapshot: BackgroundSnapshot,
) {
  const transformed = transformSummaryRealtimeSnapshot(
    snapshot as unknown as Record<string, unknown>,
  );
  if (transformed.projectId !== projectId) return;

  const current = getProjection(queryClient, projectId);
  if (!shouldApplySnapshotRevision(current.projectRevision, transformed.projectRevision)) return;

  queryClient.setQueryData<SummaryProjection>(getSummaryProjectionQueryKey(projectId), {
    projectId,
    projectRevision: transformed.projectRevision,
    statuses: transformed.summary.statuses,
    maintenance: transformed.summary.maintenance,
  });
}

function applySummaryEvent(queryClient: QueryClient, projectId: string, event: BackgroundEvent) {
  if (event.project_id !== projectId || !isSummaryBackgroundEvent(event)) return;

  const current = getProjection(queryClient, projectId);
  const eventRevision = normalizeRevision(event.project_revision);
  if (!shouldApplyEventRevision(current.projectRevision, eventRevision)) return;

  queryClient.setQueryData<SummaryProjection>(
    getSummaryProjectionQueryKey(projectId),
    reduceSummaryProjectionEvent(current, event),
  );
  applySummaryEventToListQueries(queryClient, projectId, event);
}

function useSummaryProjectionSync(projectId: string) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!projectId) return;

    const existing = summaryProjectionSubscriptions.get(projectId);
    if (existing) {
      summaryProjectionSubscriptions.set(projectId, {
        ...existing,
        count: existing.count + 1,
      });
    } else {
      const subscription = subscribeBackgroundProjection(
        projectId,
        (snapshot) => applySummarySnapshot(queryClient, projectId, snapshot),
        (event) => applySummaryEvent(queryClient, projectId, event),
      );
      summaryProjectionSubscriptions.set(projectId, { count: 1, subscription });
    }

    return () => {
      const current = summaryProjectionSubscriptions.get(projectId);
      if (!current) return;
      if (current.count <= 1) {
        current.subscription.close();
        summaryProjectionSubscriptions.delete(projectId);
        return;
      }
      summaryProjectionSubscriptions.set(projectId, {
        ...current,
        count: current.count - 1,
      });
    };
  }, [projectId, queryClient]);
}

export function useSummaryStatuses(projectId: string) {
  const queryClient = useQueryClient();
  useSummaryProjectionSync(projectId);

  return useQuery<SummaryProjection, Error, SummaryStatusItem[]>({
    queryKey: getSummaryProjectionQueryKey(projectId),
    queryFn: async () => createEmptySummaryProjection(projectId),
    enabled: false,
    initialData: () => getProjection(queryClient, projectId),
    select: (projection) => projection.statuses,
    staleTime: Infinity,
  });
}

export function useSummaryPanel(projectId: string) {
  const queryClient = useQueryClient();
  useSummaryProjectionSync(projectId);

  return useQuery<SummaryProjection, Error, SummaryPanelResponse>({
    queryKey: getSummaryProjectionQueryKey(projectId),
    queryFn: async () => createEmptySummaryProjection(projectId),
    enabled: false,
    initialData: () => getProjection(queryClient, projectId),
    select: (projection) => ({ maintenance: projection.maintenance }),
    staleTime: Infinity,
  });
}

export function useChapterSummaryListPage(
  projectId: string,
  page: number,
  volumeId?: string | null,
) {
  return useQuery<ChapterSummaryListResponse>({
    queryKey: ["chapter-summary-list", projectId, volumeId ?? "all", page, SUMMARY_PAGE_SIZE],
    queryFn: ({ signal }) =>
      fetchChapterSummaryList(projectId, page, SUMMARY_PAGE_SIZE, signal, volumeId),
    enabled: !!projectId,
    placeholderData: keepPreviousData,
    staleTime: 30 * 1000,
  });
}

export function useLongTermSummariesPage(projectId: string, page: number) {
  return useQuery<LongTermSummaryListResponse>({
    queryKey: ["long-term-summaries-page", projectId, page, SUMMARY_PAGE_SIZE],
    queryFn: ({ signal }) => fetchLongTermSummariesPage(projectId, page, SUMMARY_PAGE_SIZE, signal),
    enabled: !!projectId,
    placeholderData: keepPreviousData,
    staleTime: 30 * 1000,
  });
}

export function useEnqueueSummary(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: EnqueueSummaryRequest) => enqueueSummary(projectId, data),
    onSuccess: (result, variables) => {
      const now = new Date().toISOString();
      const optimisticStatus = result.status === "ready" ? "ready" : "queued";
      const optimisticProgressMessage = optimisticStatus === "queued" ? "已加入队列" : null;
      const optimisticJob: SummaryBackgroundJobItem | null =
        result.jobId && variables.summaryType !== "all"
          ? {
              jobId: result.jobId,
              jobType:
                variables.summaryType === "chapter"
                  ? "chapter_summary"
                  : variables.summaryType === "long_term"
                    ? "long_term_summary"
                    : "chapter_summary",
              status: optimisticStatus === "queued" ? "pending" : "running",
              chapterId: variables.chapterId ?? null,
              summaryId: result.summaryId,
              startOrder: variables.startOrder ?? null,
              endOrder: variables.endOrder ?? null,
              progressCurrent: 0,
              progressTotal: null,
              progressMessage: optimisticProgressMessage,
              errorMessage: null,
              createdAt: now,
              updatedAt: now,
            }
          : null;

      queryClient.setQueryData<SummaryProjection>(
        getSummaryProjectionQueryKey(projectId),
        (current) => {
          let next = current ?? createEmptySummaryProjection(projectId);
          if (variables.summaryType === "chapter" && variables.chapterId) {
            next = applyChapterStatusToProjection(next, {
              chapter_id: variables.chapterId,
              status: optimisticStatus,
              summary_id: result.summaryId,
              progress_message: optimisticProgressMessage,
            });
          }
          if (
            variables.summaryType === "long_term" &&
            variables.startOrder != null &&
            variables.endOrder != null
          ) {
            next = applyLongTermStatusToProjection(next, {
              start_order: variables.startOrder,
              end_order: variables.endOrder,
              status: optimisticStatus,
              summary_id: result.summaryId,
              progress_message: optimisticProgressMessage,
            });
          }
          if (!optimisticJob) return next;
          return {
            ...next,
            maintenance: {
              ...next.maintenance,
              activeJobs: [
                ...next.maintenance.activeJobs.filter((item) => item.jobId !== optimisticJob.jobId),
                optimisticJob,
              ],
            },
          };
        },
      );

      queryClient.setQueriesData(
        { queryKey: ["chapter-summary-list", projectId] },
        (current: ChapterSummaryListResponse | undefined) => {
          if (!current || variables.summaryType !== "chapter" || !variables.chapterId)
            return current;
          return {
            ...current,
            items: current.items.map((item) =>
              item.chapterId === variables.chapterId
                ? {
                    ...item,
                    status: optimisticStatus,
                    isStale: optimisticStatus === "ready" ? item.isStale : false,
                    summaryId: result.summaryId,
                  }
                : item,
            ),
          };
        },
      );

      queryClient.setQueriesData(
        { queryKey: ["long-term-summaries-page", projectId] },
        (current: LongTermSummaryListResponse | undefined) => {
          if (!current || variables.summaryType !== "long_term") return current;
          return {
            ...current,
            items: current.items.map((item) =>
              item.startOrder === variables.startOrder && item.endOrder === variables.endOrder
                ? {
                    ...item,
                    status: optimisticStatus,
                    isStale: optimisticStatus === "ready" ? item.isStale : false,
                    summaryId: result.summaryId,
                  }
                : item,
            ),
          };
        },
      );

      void queryClient.invalidateQueries({ queryKey: ["chapter-summary-list", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["long-term-summaries-page", projectId] });
    },
  });
}

export function useDeleteChapterSummaries(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (chapterIds: string[]) => deleteChapterSummaries(projectId, chapterIds),
    onMutate: async (chapterIds) => {
      await queryClient.cancelQueries({ queryKey: ["chapter-summary-list", projectId] });

      const previousChapterSummaryLists = queryClient.getQueriesData<ChapterSummaryListResponse>({
        queryKey: ["chapter-summary-list", projectId],
      });
      const previousSummaryProjection = queryClient.getQueryData<SummaryProjection>(
        getSummaryProjectionQueryKey(projectId),
      );
      const shouldClearAll = chapterIds.length === 0;
      const targetIdSet = new Set(chapterIds);

      queryClient.setQueriesData<ChapterSummaryListResponse>(
        { queryKey: ["chapter-summary-list", projectId] },
        (current) => {
          if (!current) return current;
          const nextItems = shouldClearAll
            ? []
            : current.items.filter((item) => !targetIdSet.has(item.chapterId));
          return {
            ...current,
            items: nextItems,
            total: shouldClearAll ? 0 : Math.max(0, current.total - targetIdSet.size),
          };
        },
      );

      queryClient.setQueryData<SummaryProjection>(
        getSummaryProjectionQueryKey(projectId),
        (current) => {
          if (!current) return current;
          return {
            ...current,
            statuses: current.statuses.map((item) =>
              shouldClearAll || targetIdSet.has(item.chapterId)
                ? {
                    ...item,
                    status: "not_generated",
                    isStale: false,
                    summaryId: null,
                    updatedAt: null,
                  }
                : item,
            ),
            maintenance: {
              ...current.maintenance,
              missingOrFailedChapterSummaries:
                current.maintenance.missingOrFailedChapterSummaries.map((item) =>
                  shouldClearAll || targetIdSet.has(item.chapterId)
                    ? {
                        ...item,
                        status: "not_generated",
                        isStale: false,
                        summaryId: null,
                        progressMessage: null,
                      }
                    : item,
                ),
            },
          };
        },
      );

      return { previousChapterSummaryLists, previousSummaryProjection };
    },
    onError: (_error, _chapterIds, context) => {
      context?.previousChapterSummaryLists.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data);
      });
      queryClient.setQueryData(
        getSummaryProjectionQueryKey(projectId),
        context?.previousSummaryProjection,
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["chapter-summary-list", projectId] });
    },
  });
}

export function useDeleteLongTermSummaries(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ranges: Array<[number, number]>) => deleteLongTermSummaries(projectId, ranges),
    onMutate: async (ranges) => {
      await queryClient.cancelQueries({ queryKey: ["long-term-summaries-page", projectId] });

      const previousLongTermLists = queryClient.getQueriesData<LongTermSummaryListResponse>({
        queryKey: ["long-term-summaries-page", projectId],
      });
      const previousSummaryProjection = queryClient.getQueryData<SummaryProjection>(
        getSummaryProjectionQueryKey(projectId),
      );
      const shouldClearAll = ranges.length === 0;
      const targetRangeSet = new Set(ranges.map(([s, e]) => `${s}-${e}`));

      queryClient.setQueriesData<LongTermSummaryListResponse>(
        { queryKey: ["long-term-summaries-page", projectId] },
        (current) => {
          if (!current) return current;
          const nextItems = shouldClearAll
            ? []
            : current.items.filter(
                (item) => !targetRangeSet.has(`${item.startOrder}-${item.endOrder}`),
              );
          return {
            ...current,
            items: nextItems,
            total: shouldClearAll ? 0 : Math.max(0, current.total - targetRangeSet.size),
          };
        },
      );

      queryClient.setQueryData<SummaryProjection>(
        getSummaryProjectionQueryKey(projectId),
        (current) => {
          if (!current) return current;
          return {
            ...current,
            maintenance: {
              ...current.maintenance,
              missingOrFailedLongTermSummaries:
                current.maintenance.missingOrFailedLongTermSummaries.map((item) =>
                  shouldClearAll || targetRangeSet.has(`${item.startOrder}-${item.endOrder}`)
                    ? {
                        ...item,
                        status: "not_generated",
                        isStale: false,
                        summaryId: null,
                        progressMessage: null,
                      }
                    : item,
                ),
            },
          };
        },
      );

      return { previousLongTermLists, previousSummaryProjection };
    },
    onError: (_error, _ranges, context) => {
      context?.previousLongTermLists.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data);
      });
      queryClient.setQueryData(
        getSummaryProjectionQueryKey(projectId),
        context?.previousSummaryProjection,
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["long-term-summaries-page", projectId] });
    },
  });
}
