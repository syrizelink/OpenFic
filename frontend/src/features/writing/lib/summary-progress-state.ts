import type { SummaryBackgroundJobItem, SummaryBatchProgressItem } from "@/lib/api-client";

export interface SummaryProgressState {
  status: string;
  isActive: boolean;
  totalCount: number;
  completedCount: number;
  runningCount: number;
  queuedCount: number;
  currentMessage: string;
  currentProgressValue: number | null;
}

export function shouldShowSummaryProgressPanel(
  state: SummaryProgressState | null,
): state is SummaryProgressState {
  return Boolean(state?.isActive);
}

export function buildSummaryProgressState(
  batchProgress: SummaryBatchProgressItem | null,
  activeJobs: SummaryBackgroundJobItem[],
): SummaryProgressState | null {
  if (!batchProgress) return null;

  const queuedCount = Math.max(batchProgress.queuedItemCount, 0);
  const runningCount = Math.max(batchProgress.runningItemCount, 0);
  const completedCount = Math.max(batchProgress.completedItemCount, 0);
  const totalCount = Math.max(
    batchProgress.totalItemCount,
    completedCount + queuedCount + runningCount,
  );
  const runningJob = activeJobs.find((job) => job.status === "running");
  const isActive =
    batchProgress.status === "pending" ||
    batchProgress.status === "running" ||
    batchProgress.status === "cancel_requested";
  const currentMessage =
    (batchProgress.status === "cancel_requested" ? "batch_cancelling" : null) ??
    (batchProgress.status === "cancelled" ? "batch_cancelled" : null) ??
    (!isActive && totalCount > 0 && completedCount >= totalCount ? "batch_completed" : null) ??
    runningJob?.progressMessage ??
    batchProgress.progressMessage ??
    (runningCount > 0 ? "batch_generating" : queuedCount > 0 ? "batch_queued" : "batch_processing");

  return {
    status: batchProgress.status,
    isActive,
    totalCount,
    completedCount,
    runningCount,
    queuedCount,
    currentMessage,
    currentProgressValue: batchProgress.progressPercent,
  };
}
