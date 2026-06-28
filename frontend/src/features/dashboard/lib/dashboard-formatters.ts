export const EMPTY_VALUE = "__all__";

const statusLabels: Record<string, string> = {
  success: "已完成",
  error: "失败",
  cancelled: "已取消",
  running: "进行中",
};

const agentLabels: Record<string, string> = {
  primary: "主代理",
  explorer: "信息探索",
  composer: "规划编排",
  auditor: "计划审查",
  writer: "正文写作",
  actor: "任务执行",
  reviewer: "审阅修改",
};

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(Math.round(value));
}

export function formatSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${(value / 1000).toFixed(2)} s`;
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
  return statusLabels[value] ?? value;
}

export function getAgentLabel(value: string): string {
  return agentLabels[value] ?? value;
}

export function toIsoDateTime(value: string | undefined, boundary: "start" | "end"): string | undefined {
  if (!value) return undefined;
  const suffix = boundary === "start" ? "T00:00:00" : "T23:59:59";
  return `${value}${suffix}`;
}
