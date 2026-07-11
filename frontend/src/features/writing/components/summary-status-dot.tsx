import { Tooltip } from "@radix-ui/themes";

import type { SummaryStatus } from "@/lib/api-client";

import "./summary-status-dot.css";

interface SummaryStatusDotProps {
  status?: SummaryStatus;
  isStale?: boolean;
  onOpenSummary?: () => void;
}

const STATUS_LABELS: Record<SummaryStatus, string> = {
  not_generated: "未生成摘要",
  queued: "摘要排队中",
  running: "摘要生成中",
  ready: "摘要就绪",
  failed: "摘要生成失败",
};

const STATUS_COLORS: Record<SummaryStatus, string> = {
  not_generated: "var(--gray-7)",
  queued: "var(--amber-8)",
  running: "var(--blue-8)",
  ready: "var(--green-8)",
  failed: "var(--red-8)",
};

export function SummaryStatusDot({
  status = "not_generated",
  isStale = false,
  onOpenSummary,
}: SummaryStatusDotProps) {
  const label = status === "ready" && isStale ? "摘要待更新" : STATUS_LABELS[status];
  const color = status === "ready" && isStale ? "var(--orange-8)" : STATUS_COLORS[status];
  return (
    <Tooltip content={label}>
      <button
        type="button"
        aria-label={label}
        className="summary-status-dot-button"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation();
          onOpenSummary?.();
        }}
      >
        <span
          className={status === "running" ? "summary-status-dot is-running" : "summary-status-dot"}
          style={{ backgroundColor: color }}
        />
      </button>
    </Tooltip>
  );
}
