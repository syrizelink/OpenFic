import i18n from "@/i18n";

import type {
  DashboardBreakdownItem,
  DashboardModelTimeSeriesPoint,
  DashboardStatsResponse,
  WritingActivityTimeSeriesPoint,
} from "./dashboard.types";

export type DashboardChartValueFormat = "number" | "seconds" | "compact";
export type DashboardChartTooltipUnit = "words" | "days" | "calls" | "tokens" | "seconds";
export type DashboardChartAxisFormat = "month-day";

export interface DashboardChartTooltip {
  fixedLabel?: string;
  unit: DashboardChartTooltipUnit;
}

export interface DashboardLineSeries {
  id: string;
  data: Array<{ x: string; y: number }>;
}

export interface DashboardBarDatum {
  label: string;
  [key: string]: string | number;
}

export interface DashboardPieDatum {
  id: string;
  label: string;
  value: number;
}

export type DashboardChartModel =
  | {
      kind: "line";
      data: DashboardLineSeries[];
      valueFormat?: DashboardChartValueFormat;
      xAxisFormat?: DashboardChartAxisFormat;
      enableArea?: boolean;
      tooltip?: DashboardChartTooltip;
    }
  | {
      kind: "bar";
      data: DashboardBarDatum[];
      keys: string[];
      valueFormat?: DashboardChartValueFormat;
      xAxisFormat?: DashboardChartAxisFormat;
      groupMode?: "grouped" | "stacked";
      tooltip?: DashboardChartTooltip;
    }
  | {
      kind: "pie";
      data: DashboardPieDatum[];
      valueFormat?: DashboardChartValueFormat;
      tooltip?: DashboardChartTooltip;
    };

function getRecentDates(data: DashboardStatsResponse | undefined): string[] {
  return Array.from(new Set((data?.modelTimeSeries ?? []).map((item) => item.date))).slice(-7);
}

function getTopModels(data: DashboardStatsResponse | undefined): DashboardBreakdownItem[] {
  return (data?.byModel ?? []).slice(0, 5);
}

function getOptionLabel(
  options: DashboardStatsResponse["options"] | undefined,
  kind: "model" | "project",
  value: string,
  fallback: string,
): string {
  const items = kind === "model" ? options?.modelOptions : options?.projectOptions;
  return items?.find((item) => item.value === value)?.label ?? fallback;
}

function getModelPointMap(
  points: DashboardModelTimeSeriesPoint[],
): Map<string, DashboardModelTimeSeriesPoint> {
  return new Map(points.map((point) => [`${point.date}:${point.key}`, point]));
}

export function buildModelTrendOption(
  data: DashboardStatsResponse | undefined,
  key: "calls" | "avgLatencyMs",
): DashboardChartModel {
  const dates = getRecentDates(data);
  const models = getTopModels(data);
  const points = (data?.modelTimeSeries ?? []).filter((point) => dates.includes(point.date));
  const pointMap = getModelPointMap(points);
  return {
    kind: "line",
    enableArea: true,
    valueFormat: key === "avgLatencyMs" ? "seconds" : "compact",
    xAxisFormat: "month-day",
    tooltip: { unit: key === "avgLatencyMs" ? "seconds" : "calls" },
    data: models.map((model) => ({
      id: getOptionLabel(data?.options, "model", model.key, model.label),
      data: dates.map((date) => ({ x: date, y: pointMap.get(`${date}:${model.key}`)?.[key] ?? 0 })),
    })),
  };
}

export function buildModelTokenTrendOption(
  data: DashboardStatsResponse | undefined,
): DashboardChartModel {
  const dates = getRecentDates(data);
  const models = getTopModels(data);
  const points = (data?.modelTimeSeries ?? []).filter((point) => dates.includes(point.date));
  const pointMap = getModelPointMap(points);
  return {
    kind: "bar",
    keys: models.map((model) => getOptionLabel(data?.options, "model", model.key, model.label)),
    valueFormat: "compact",
    xAxisFormat: "month-day",
    tooltip: { unit: "tokens" },
    data: dates.map((date) => {
      const item: DashboardBarDatum = { label: date };
      for (const model of models) {
        item[getOptionLabel(data?.options, "model", model.key, model.label)] = pointMap.get(
          `${date}:${model.key}`,
        )?.tokensTotal ?? 0;
      }
      return item;
    }),
  };
}

export function buildRoundedDonutOption(
  items: DashboardBreakdownItem[],
  valueKey: "calls" | "tokensTotal",
  _name: string,
  options?: DashboardStatsResponse["options"],
  labelKind: "model" | "project" = "model",
): DashboardChartModel {
  return {
    kind: "pie",
    tooltip: { unit: valueKey === "calls" ? "calls" : "tokens" },
    data: items
      .map((item) => ({
        id: item.key,
        label: getOptionLabel(options, labelKind, item.key, item.label),
        value: item[valueKey],
      }))
      .filter((item) => item.value > 0),
  };
}

export function buildWritingTrendOption(
  points: WritingActivityTimeSeriesPoint[],
): DashboardChartModel {
  const createdKey = i18n.t("dashboard.charts.writingSeriesCreated");
  const importedKey = i18n.t("dashboard.charts.writingSeriesImported");
  return {
    kind: "bar",
    keys: [createdKey, importedKey],
    groupMode: "stacked",
    valueFormat: "compact",
    xAxisFormat: "month-day",
    tooltip: { unit: "words" },
    data: points.map((item) => ({
      label: item.date,
      [createdKey]: item.userWordDelta + item.agentWordDelta,
      [importedKey]: item.importWordDelta,
    })),
  };
}

export function buildWritingCumulativeOption(
  points: WritingActivityTimeSeriesPoint[],
): DashboardChartModel {
  let total = 0;
  return {
    kind: "line",
    enableArea: true,
    xAxisFormat: "month-day",
    tooltip: { fixedLabel: i18n.t("dashboard.charts.cumulativeSeries"), unit: "words" },
    data: [
      {
        id: i18n.t("dashboard.charts.cumulativeSeries"),
        data: points.map((item) => {
          total += Math.max(0, item.userWordDelta + item.agentWordDelta);
          return { x: item.date, y: total };
        }),
      },
    ],
  };
}

export function buildWritingSourceOption(
  points: WritingActivityTimeSeriesPoint[],
): DashboardChartModel {
  const userTotal = points.reduce((total, item) => total + Math.max(0, item.userWordDelta), 0);
  const agentTotal = points.reduce((total, item) => total + Math.max(0, item.agentWordDelta), 0);
  const importTotal = points.reduce((total, item) => total + Math.max(0, item.importWordDelta), 0);
  return {
    kind: "pie",
    tooltip: { unit: "words" },
    data: [
      { id: "user", label: i18n.t("dashboard.charts.sourceUserEdit"), value: userTotal },
      { id: "agent", label: i18n.t("dashboard.charts.sourceAgentEdit"), value: agentTotal },
      { id: "import", label: i18n.t("dashboard.charts.sourceImport"), value: importTotal },
    ].filter((item) => item.value > 0),
  };
}

export function buildWritingWeekdayOption(
  points: WritingActivityTimeSeriesPoint[],
): DashboardChartModel {
  const labels = [
    i18n.t("dashboard.charts.weekdayMon"),
    i18n.t("dashboard.charts.weekdayTue"),
    i18n.t("dashboard.charts.weekdayWed"),
    i18n.t("dashboard.charts.weekdayThu"),
    i18n.t("dashboard.charts.weekdayFri"),
    i18n.t("dashboard.charts.weekdaySat"),
    i18n.t("dashboard.charts.weekdaySun"),
  ];
  const activeDayCounts = Array.from({ length: 7 }, () => 0);
  for (const item of points) {
    const creativeWords = Math.max(0, item.userWordDelta + item.agentWordDelta);
    if (creativeWords <= 0) continue;
    const weekday = new Date(`${item.date}T00:00:00`).getDay();
    const mondayFirstIndex = weekday === 0 ? 6 : weekday - 1;
    activeDayCounts[mondayFirstIndex] += 1;
  }
  return {
    kind: "bar",
    keys: [i18n.t("dashboard.charts.activeDaysSeries")],
    tooltip: { fixedLabel: i18n.t("dashboard.charts.activeDaysTooltipLabel"), unit: "days" },
    data: labels.map((label, index) => ({ label, [i18n.t("dashboard.charts.activeDaysSeries")]: activeDayCounts[index] })),
  };
}
