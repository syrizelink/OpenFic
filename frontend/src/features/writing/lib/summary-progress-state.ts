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
  const isActive = batchProgress.status === "pending" || batchProgress.status === "running";
  const currentMessage =
    (!isActive && totalCount > 0 && completedCount >= totalCount ? "摘要生成完成" : null) ??
    runningJob?.progressMessage ??
    batchProgress.progressMessage ??
    (runningCount > 0 ? "正在生成摘要" : queuedCount > 0 ? "摘要已加入队列" : "摘要处理中");

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
