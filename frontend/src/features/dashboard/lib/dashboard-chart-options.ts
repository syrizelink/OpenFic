import type { DashboardBreakdownItem, DashboardModelTimeSeriesPoint, DashboardStatsResponse, WritingActivityTimeSeriesPoint } from "./dashboard.types";
import type { DashboardEchartsThemeMode } from "./dashboard-echarts-theme";

export type DashboardChartOption = Record<string, unknown>;

const brightBarStyle = {
  borderRadius: [6, 6, 0, 0],
};

const roundedDonutStyle = {
  borderRadius: 8,
  borderColor: "var(--color-panel-solid)",
  borderWidth: 2,
};

const softLineAreaStyle = {
  color: {
    type: "linear",
    x: 0,
    y: 0,
    x2: 0,
    y2: 1,
    colorStops: [
      { offset: 0, color: "rgba(14, 165, 233, 0.22)" },
      { offset: 1, color: "rgba(14, 165, 233, 0.02)" },
    ],
  },
};

export function withDashboardChartTheme(option: DashboardChartOption, mode: DashboardEchartsThemeMode): DashboardChartOption {
  if (mode === "light") return option;
  return {
    ...option,
    tooltip: {
      backgroundColor: "#1f1f1f",
      borderColor: "#3a3a3a",
      textStyle: { color: "#f1f1f1" },
      ...(option.tooltip as Record<string, unknown> | undefined),
    },
    legend: {
      textStyle: { color: "#d8d8d8" },
      ...(option.legend as Record<string, unknown> | undefined),
    },
    xAxis: {
      axisLine: { lineStyle: { color: "#5a5a5a" } },
      axisTick: { lineStyle: { color: "#5a5a5a" } },
      axisLabel: { color: "#cfcfcf" },
      splitLine: { lineStyle: { color: "#333333" } },
      ...(option.xAxis as Record<string, unknown> | undefined),
    },
    yAxis: {
      axisLine: { lineStyle: { color: "#5a5a5a" } },
      axisTick: { lineStyle: { color: "#5a5a5a" } },
      axisLabel: { color: "#cfcfcf" },
      splitLine: { lineStyle: { color: "#333333" } },
      ...(option.yAxis as Record<string, unknown> | undefined),
    },
  };
}

function getRecentDates(data: DashboardStatsResponse | undefined): string[] {
  return Array.from(new Set((data?.modelTimeSeries ?? []).map((item) => item.date))).slice(-7);
}

function getTopModels(data: DashboardStatsResponse | undefined): DashboardBreakdownItem[] {
  return (data?.byModel ?? []).slice(0, 5);
}

function getModelPointMap(points: DashboardModelTimeSeriesPoint[]): Map<string, DashboardModelTimeSeriesPoint> {
  return new Map(points.map((point) => [`${point.date}:${point.key}`, point]));
}

function buildAxisTooltipWithTotal(formatter?: (value: number) => string) {
  return (params: unknown) => {
    if (!Array.isArray(params)) return "";
    const title = String((params[0] as { axisValueLabel?: string; axisValue?: string })?.axisValueLabel ?? (params[0] as { axisValue?: string })?.axisValue ?? "");
    const rows = params as Array<{ marker?: string; seriesName?: string; value?: number }>;
    const total = rows.reduce((sum, item) => sum + Number(item.value ?? 0), 0);
    const format = formatter ?? ((value: number) => String(Math.round(value)));
    return [
      title,
      ...rows.map((item) => `${item.marker ?? ""} ${item.seriesName ?? ""}: ${format(Number(item.value ?? 0))}`),
      `总量: ${format(total)}`,
    ].join("<br />");
  };
}

export function buildModelTrendOption(
  data: DashboardStatsResponse | undefined,
  key: "calls" | "avgLatencyMs"
): DashboardChartOption {
  const dates = getRecentDates(data);
  const models = getTopModels(data);
  const points = (data?.modelTimeSeries ?? []).filter((point) => dates.includes(point.date));
  const pointMap = getModelPointMap(points);
  const isLatency = key === "avgLatencyMs";
  return {
    tooltip: {
      trigger: "axis",
      formatter: buildAxisTooltipWithTotal(isLatency ? (value) => `${(value / 1000).toFixed(2)} s` : undefined),
    },
    legend: { top: 0, right: 0, type: "scroll" },
    grid: { top: 46, left: 48, right: 24, bottom: 34 },
    xAxis: { type: "category", data: dates, axisTick: { show: false } },
    yAxis: { type: "value" },
    series: models.map((model) => ({
      name: model.label,
      type: "line",
      smooth: true,
      showSymbol: false,
      data: dates.map((date) => pointMap.get(`${date}:${model.key}`)?.[key] ?? 0),
    })),
  };
}

export function buildModelTokenTrendOption(data: DashboardStatsResponse | undefined): DashboardChartOption {
  const dates = getRecentDates(data);
  const models = getTopModels(data);
  const points = (data?.modelTimeSeries ?? []).filter((point) => dates.includes(point.date));
  const pointMap = getModelPointMap(points);
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { top: 0, right: 0, type: "scroll" },
    grid: { top: 46, left: 54, right: 24, bottom: 34 },
    xAxis: { type: "category", data: dates, axisTick: { show: false } },
    yAxis: { type: "value" },
    series: models.map((model) => ({
      name: model.label,
      type: "bar",
      barMaxWidth: 20,
      itemStyle: brightBarStyle,
      data: dates.map((date) => pointMap.get(`${date}:${model.key}`)?.tokensTotal ?? 0),
    })),
  };
}

export function buildRoundedDonutOption(
  items: DashboardBreakdownItem[],
  valueKey: "calls" | "tokensTotal",
  name: string
): DashboardChartOption {
  return {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { bottom: 0, left: "center", type: "scroll" },
    series: [
      {
        name,
        type: "pie",
        radius: ["52%", "74%"],
        center: ["50%", "42%"],
        avoidLabelOverlap: true,
        padAngle: 2,
        itemStyle: roundedDonutStyle,
        data: items.map((item) => ({ name: item.label, value: item[valueKey] })).filter((item) => item.value > 0),
        label: { formatter: "{b}\n{d}%" },
      },
    ],
  };
}

export function buildWritingTrendOption(points: WritingActivityTimeSeriesPoint[]): DashboardChartOption {
  return {
    tooltip: { trigger: "axis" },
    legend: { top: 0, right: 0 },
    grid: { top: 42, left: 48, right: 24, bottom: 34 },
    xAxis: { type: "category", data: points.map((item) => item.date), axisTick: { show: false } },
    yAxis: { type: "value" },
    series: [
      { name: "创作", type: "bar", stack: "words", barMaxWidth: 28, itemStyle: brightBarStyle, data: points.map((item) => item.userWordDelta + item.agentWordDelta) },
      { name: "导入", type: "bar", stack: "words", barMaxWidth: 28, itemStyle: brightBarStyle, data: points.map((item) => item.importWordDelta) },
    ],
  };
}

export function buildWritingCumulativeOption(points: WritingActivityTimeSeriesPoint[]): DashboardChartOption {
  let total = 0;
  const cumulative = points.map((item) => {
    total += Math.max(0, item.userWordDelta + item.agentWordDelta);
    return total;
  });
  return {
    tooltip: { trigger: "axis" },
    grid: { top: 28, left: 48, right: 24, bottom: 34 },
    xAxis: { type: "category", data: points.map((item) => item.date), axisTick: { show: false } },
    yAxis: { type: "value" },
    series: [
      {
        name: "累计创作",
        type: "line",
        smooth: true,
        showSymbol: false,
        areaStyle: softLineAreaStyle,
        data: cumulative,
      },
    ],
  };
}

export function buildWritingSourceOption(points: WritingActivityTimeSeriesPoint[]): DashboardChartOption {
  const userTotal = points.reduce((total, item) => total + Math.max(0, item.userWordDelta), 0);
  const agentTotal = points.reduce((total, item) => total + Math.max(0, item.agentWordDelta), 0);
  const importTotal = points.reduce((total, item) => total + Math.max(0, item.importWordDelta), 0);
  return {
    tooltip: { trigger: "item" },
    legend: { bottom: 0, left: "center" },
    series: [
      {
        name: "字数来源",
        type: "pie",
        radius: ["46%", "70%"],
        center: ["50%", "42%"],
        data: [
          { name: "用户编辑", value: userTotal },
          { name: "Agent 修改", value: agentTotal },
          { name: "导入初始化", value: importTotal },
        ],
        label: { formatter: "{b}: {c}" },
      },
    ],
  };
}

export function buildWritingWeekdayOption(points: WritingActivityTimeSeriesPoint[]): DashboardChartOption {
  const labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
  const activeDayCounts = Array.from({ length: 7 }, () => 0);
  for (const item of points) {
    const creativeWords = Math.max(0, item.userWordDelta + item.agentWordDelta);
    if (creativeWords <= 0) continue;
    const weekday = new Date(`${item.date}T00:00:00`).getDay();
    const mondayFirstIndex = weekday === 0 ? 6 : weekday - 1;
    activeDayCounts[mondayFirstIndex] += 1;
  }
  return {
    tooltip: { trigger: "axis" },
    grid: { top: 28, left: 46, right: 24, bottom: 34 },
    xAxis: { type: "category", data: labels, axisTick: { show: false } },
    yAxis: { type: "value" },
    series: [{ name: "活跃天数", type: "bar", barMaxWidth: 24, itemStyle: brightBarStyle, data: activeDayCounts }],
  };
}
