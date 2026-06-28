import type {
  BackgroundEvent,
  SummaryBackgroundJobItem,
  SummaryMaintenance,
} from "@/lib/api-client";

export const ITEM_TERMINAL_EVENT_TYPES = new Set([
  "background_item_succeeded",
  "background_item_failed",
  "background_item_skipped",
]);

function getString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function getNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function resolveProgressMessage(payload: Record<string, unknown>, current: string | null): string | null {
  if ("progress_message" in payload) return getString(payload.progress_message);
  if ("message" in payload) return getString(payload.message);
  return current;
}

export function extractBatchProgressFromEvent(
  event: BackgroundEvent,
  current: SummaryMaintenance["batchProgress"]
): SummaryMaintenance["batchProgress"] {
  if (!event.job_id || !event.payload) return current;
  const payload = event.payload;
  const progressCurrent = getNumber(payload.current) ?? getNumber(payload.progress_current) ?? current?.progressCurrent ?? 0;
  const progressTotal = getNumber(payload.total) ?? getNumber(payload.progress_total) ?? current?.progressTotal ?? null;
  const completedItemCount = getNumber(payload.completed_item_count) ?? current?.completedItemCount ?? 0;
  const totalItemCount = getNumber(payload.total_item_count) ?? current?.totalItemCount ?? 0;
  return {
    jobId: event.job_id,
    status: getString(payload.status) ?? current?.status ?? "running",
    progressCurrent,
    progressTotal,
    progressPercent:
      getNumber(payload.progress_percent)
      ?? current?.progressPercent
      ?? (totalItemCount > 0 ? Math.round((completedItemCount / totalItemCount) * 100) : null),
    progressMessage: getString(payload.message) ?? getString(payload.progress_message) ?? current?.progressMessage ?? null,
    totalItemCount,
    completedItemCount,
    runningItemCount: getNumber(payload.running_item_count) ?? current?.runningItemCount ?? 0,
    queuedItemCount: getNumber(payload.queued_item_count) ?? current?.queuedItemCount ?? 0,
    createdAt: current?.createdAt ?? (event.created_at || new Date().toISOString()),
    updatedAt: event.created_at ?? current?.updatedAt ?? new Date().toISOString(),
  };
}

function hasAuthoritativeProgress(current: SummaryMaintenance["batchProgress"] | null): boolean {
  return Boolean(current && (current.progressTotal != null || current.progressPercent != null || current.totalItemCount > 0));
}

export function updateBatchProgressForItemEvent(
  current: SummaryMaintenance["batchProgress"],
  event: BackgroundEvent,
  previousJob: SummaryBackgroundJobItem | undefined
): SummaryMaintenance["batchProgress"] {
  const jobId = getString(event.job_id) ?? current?.jobId;
  if (!jobId) return current;

  const now = event.created_at ?? new Date().toISOString();
  const payload = event.payload ?? {};
  const totalDelta = event.type === "background_item_queued" && !previousJob ? 1 : 0;
  let totalItemCount = (current?.totalItemCount ?? 0) + totalDelta;
  let completedItemCount = current?.completedItemCount ?? 0;
  let runningItemCount = current?.runningItemCount ?? 0;
  let queuedItemCount = current?.queuedItemCount ?? 0;

  if (event.type === "background_item_queued" && !previousJob) {
    queuedItemCount += 1;
  }

  if (event.type === "background_item_progress") {
    if (!previousJob) {
      runningItemCount += 1;
    } else if (previousJob.status !== "running") {
      queuedItemCount = Math.max(queuedItemCount - 1, 0);
      runningItemCount += 1;
    }
  }

  if (ITEM_TERMINAL_EVENT_TYPES.has(event.type)) {
    if (previousJob?.status === "running") {
      runningItemCount = Math.max(runningItemCount - 1, 0);
    } else if (previousJob) {
      queuedItemCount = Math.max(queuedItemCount - 1, 0);
    }
    completedItemCount += 1;
  }

  totalItemCount = Math.max(totalItemCount, completedItemCount + runningItemCount + queuedItemCount);
  const nextProgressMessage = resolveProgressMessage(payload, current?.progressMessage ?? null);

  if (!hasAuthoritativeProgress(current)) {
    return {
      jobId,
      status: current?.status ?? "running",
      progressCurrent: 0,
      progressTotal: null,
      progressPercent: null,
      progressMessage: nextProgressMessage,
      totalItemCount,
      completedItemCount,
      runningItemCount,
      queuedItemCount,
      createdAt: current?.createdAt ?? now,
      updatedAt: now,
    };
  }

  return {
    jobId,
    status: current?.status ?? "running",
    progressCurrent: current?.progressCurrent ?? 0,
    progressTotal: current?.progressTotal ?? null,
    progressPercent: current?.progressPercent ?? null,
    progressMessage: nextProgressMessage,
    totalItemCount,
    completedItemCount,
    runningItemCount,
    queuedItemCount,
    createdAt: current?.createdAt ?? now,
    updatedAt: now,
  };
}
