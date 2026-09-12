import { Tooltip } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import type { SummaryStatus } from "@/lib/api-client";

import "./summary-status-dot.css";

interface SummaryStatusDotProps {
  status?: SummaryStatus;
  isStale?: boolean;
  onOpenSummary?: () => void;
}

const STATUS_LABEL_KEYS: Record<SummaryStatus, string> = {
  not_generated: "summary.statusDot.notGenerated",
  queued: "summary.statusDot.queued",
  running: "summary.statusDot.running",
  ready: "summary.statusDot.ready",
  failed: "summary.statusDot.failed",
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
  const { t } = useTranslation();
  const label =
    status === "ready" && isStale ? t("summary.statusDot.stale") : t(STATUS_LABEL_KEYS[status]);
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
