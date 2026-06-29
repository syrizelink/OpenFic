import i18n from "@/i18n";

export const EMPTY_VALUE = "__all__";

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(Math.round(value));
}

export function formatSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${(value / 1000).toFixed(2)}${i18n.t("dashboard.metrics.secondsSuffix")}`;
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

export function getStatusLabel(value: string): string {
  if (value === "success") return i18n.t("dashboard.status.success");
  if (value === "error") return i18n.t("dashboard.status.error");
  if (value === "cancelled") return i18n.t("dashboard.status.cancelled");
  if (value === "running") return i18n.t("dashboard.status.running");
  return value;
}

export function getAgentLabel(value: string): string {
  if (value === "primary") return i18n.t("dashboard.agentLabels.primary");
  if (value === "explorer") return i18n.t("dashboard.agentLabels.explorer");
  if (value === "composer") return i18n.t("dashboard.agentLabels.composer");
  if (value === "auditor") return i18n.t("dashboard.agentLabels.auditor");
  if (value === "writer") return i18n.t("dashboard.agentLabels.writer");
  if (value === "actor") return i18n.t("dashboard.agentLabels.actor");
  if (value === "reviewer") return i18n.t("dashboard.agentLabels.reviewer");
  return value;
}

export function toIsoDateTime(value: string | undefined, boundary: "start" | "end"): string | undefined {
  if (!value) return undefined;
  const suffix = boundary === "start" ? "T00:00:00" : "T23:59:59";
  return `${value}${suffix}`;
}
