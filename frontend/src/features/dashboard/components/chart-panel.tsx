import { ResponsiveBar, type BarTooltipProps } from "@nivo/bar";
import { ResponsiveLine, type SliceTooltipProps } from "@nivo/line";
import { ResponsivePie, type PieTooltipProps } from "@nivo/pie";
import { Card } from "@radix-ui/themes";
import { type CSSProperties, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";

import type {
  DashboardBarDatum,
  DashboardChartAxisFormat,
  DashboardChartModel,
  DashboardChartTooltipUnit,
  DashboardChartValueFormat,
  DashboardLineSeries,
  DashboardPieDatum,
} from "../lib/dashboard-chart-options";

interface ChartPanelProps {
  title: string;
  option: DashboardChartModel;
  isLoading: boolean;
  size?: "wide" | "medium" | "small";
  renderPriority?: number;
}

const chartRenderStaggerMs = 90;
const dashboardChartFontFamily = "var(--app-font-family)";
const dashboardChartLegendColors = ["#4f7d63", "#c98263", "#667894", "#9a8f57", "#7d6b5f"];
const dashboardChartTextTheme = {
  background: "transparent",
  fontFamily: dashboardChartFontFamily,
  axis: {
    domain: { line: { stroke: "var(--gray-a6)" } },
    ticks: {
      line: { stroke: "var(--gray-a6)" },
      text: { fill: "var(--gray-11)", fontFamily: dashboardChartFontFamily, fontSize: 13 },
    },
    legend: {
      text: { fill: "var(--gray-11)", fontFamily: dashboardChartFontFamily, fontSize: 13 },
    },
  },
  grid: { line: { stroke: "var(--gray-a4)" } },
  crosshair: { line: { stroke: "var(--gray-12)", strokeWidth: 1 } },
  legends: { text: { fill: "var(--gray-11)", fontFamily: dashboardChartFontFamily, fontSize: 13 } },
  labels: { text: { fill: "var(--gray-12)", fontFamily: dashboardChartFontFamily, fontSize: 13 } },
  tooltip: {
    container: {
      minWidth: "120px",
      borderColor: "var(--gray-a6)",
      background: "var(--color-panel-solid)",
      color: "var(--gray-12)",
      fontFamily: dashboardChartFontFamily,
      fontSize: "13px",
      whiteSpace: "nowrap",
    },
  },
};

function formatChartValue(value: number, format: DashboardChartValueFormat = "number"): string {
  if (format === "seconds") return `${Math.round(value / 1000)} s`;
  if (format === "compact") {
    const absoluteValue = Math.abs(value);
    if (absoluteValue >= 1_000_000_000)
      return `${(value / 1_000_000_000).toFixed(1).replace(/\.0$/, "")} b`;
    if (absoluteValue >= 1_000_000)
      return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")} m`;
    if (absoluteValue >= 1_000) return `${(value / 1_000).toFixed(1).replace(/\.0$/, "")} k`;
  }
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value);
}

function formatAxisValue(
  value: string | number,
  format: DashboardChartAxisFormat | undefined,
): string {
  const text = String(value);
  if (format === "month-day") return text.slice(5);
  return text;
}

function formatTooltipValue(value: number, unit: DashboardChartTooltipUnit): string {
  if (unit === "seconds") return (value / 1000).toFixed(2);
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value);
}

function getTooltipUnitKey(unit: DashboardChartTooltipUnit): string {
  if (unit === "words") return "dashboard.charts.tooltipUnitWords";
  if (unit === "days") return "dashboard.charts.tooltipUnitDays";
  if (unit === "calls") return "dashboard.charts.tooltipUnitCalls";
  if (unit === "tokens") return "dashboard.charts.tooltipUnitTokens";
  return "dashboard.charts.tooltipUnitSeconds";
}

function hasChartData(option: DashboardChartModel): boolean {
  if (option.kind === "line") {
    return option.data.some((series) => series.data.some((item) => item.y !== 0));
  }
  if (option.kind === "bar") {
    return option.data.some((item) =>
      option.keys.some((key) => typeof item[key] === "number" && item[key] !== 0),
    );
  }
  return option.data.some((item) => item.value !== 0);
}

function getChartMaxValue(option: DashboardChartModel): number {
  if (option.kind === "line") {
    return Math.max(0, ...option.data.flatMap((series) => series.data.map((item) => item.y)));
  }
  if (option.kind === "bar") {
    return Math.max(
      0,
      ...option.data.flatMap((item) =>
        option.keys.map((key) => (typeof item[key] === "number" ? item[key] : 0)),
      ),
    );
  }
  return Math.max(0, ...option.data.map((item) => item.value));
}

function getChartMinValue(option: DashboardChartModel): number {
  if (option.kind === "line") {
    const values = option.data.flatMap((series) => series.data.map((item) => item.y));
    return values.length > 0 ? Math.min(...values) : 0;
  }
  if (option.kind === "bar") {
    const values = option.data.flatMap((item) =>
      option.keys.map((key) => (typeof item[key] === "number" ? item[key] : 0)),
    );
    return values.length > 0 ? Math.min(...values) : 0;
  }
  const values = option.data.map((item) => item.value);
  return values.length > 0 ? Math.min(...values) : 0;
}

function getIntegerTickValues(maxValue: number): number[] | undefined {
  if (maxValue <= 0) return undefined;
  if (maxValue <= 6) return Array.from({ length: Math.ceil(maxValue) + 1 }, (_, index) => index);
  return undefined;
}

function getXAxisFormat(option: DashboardChartModel): DashboardChartAxisFormat | undefined {
  if (option.kind === "pie") return undefined;
  return option.xAxisFormat;
}

interface TooltipContent {
  label: string;
  value: string;
  unit: string;
}

function getTooltipContent(
  option: DashboardChartModel,
  label: string,
  value: number,
): TooltipContent {
  const tooltip = option.tooltip;
  const unit = tooltip?.unit ?? (option.valueFormat === "seconds" ? "seconds" : "calls");
  const displayLabel = tooltip?.fixedLabel ?? label;
  return {
    label: displayLabel,
    value: formatTooltipValue(value, unit),
    unit: getTooltipUnitKey(unit),
  };
}

function TooltipText({ content }: { content: TooltipContent }) {
  const { t } = useTranslation();

  return (
    <span>
      {content.label} <strong className="dashboard-chart-tooltip-value">{content.value}</strong>{" "}
      {t(content.unit)}
    </span>
  );
}

function ChartTooltip({ color, content }: { color?: string; content: TooltipContent }) {
  return (
    <div className="dashboard-chart-tooltip">
      <div className="dashboard-chart-tooltip-row">
        {color ? (
          <span
            className="dashboard-chart-tooltip-chip"
            style={getTooltipChipStyle(color)}
          />
        ) : null}
        <TooltipText content={content} />
      </div>
    </div>
  );
}

interface ChartTooltipRow {
  color: string;
  content: TooltipContent;
}

function getTooltipChipStyle(color: string): CSSProperties {
  return { "--dashboard-chart-tooltip-chip-color": color } as CSSProperties;
}

function ChartTooltipRows({ rows }: { rows: ChartTooltipRow[] }) {
  return (
    <div className="dashboard-chart-tooltip">
      {rows.map((row, index) => (
        <div
          key={`${row.color}:${row.content.label}:${row.content.value}:${index}`}
          className="dashboard-chart-tooltip-row"
        >
          <span
            className="dashboard-chart-tooltip-chip"
            style={getTooltipChipStyle(row.color)}
          />
          <TooltipText content={row.content} />
        </div>
      ))}
    </div>
  );
}

function ChartLegend({ items }: { items: Array<{ color: string; label: string }> }) {
  if (items.length === 0) return null;

  return (
    <div className="dashboard-chart-legend">
      {items.map((item) => (
        <div
          key={`${item.color}:${item.label}`}
          className="dashboard-chart-legend-item"
        >
          <span
            className="dashboard-chart-legend-chip"
            style={getTooltipChipStyle(item.color)}
          />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export function ChartPanel({
  title,
  option,
  isLoading,
  size = "medium",
  renderPriority = 0,
}: ChartPanelProps) {
  const { t } = useTranslation();
  const hasData = hasChartData(option);
  const [canRenderChart, setCanRenderChart] = useState(false);
  const shouldShowLoadingState = (isLoading && !hasData) || (hasData && !canRenderChart);
  const shouldShowEmptyState = !isLoading && !hasData;
  const yTickValues = getIntegerTickValues(getChartMaxValue(option));
  const areaBaselineValue = getChartMinValue(option);
  const valueFormat = (value: number) => formatChartValue(value, option.valueFormat);
  const xAxisFormat = (value: string | number) => formatAxisValue(value, getXAxisFormat(option));
  const lineTooltip = ({ slice }: SliceTooltipProps<DashboardLineSeries>) => (
    <ChartTooltipRows
      rows={slice.points.map((point) => ({
        color: point.seriesColor,
        content: getTooltipContent(option, String(point.seriesId), Number(point.data.y ?? 0)),
      }))}
    />
  );
  const barTooltip = ({ color, id, value }: BarTooltipProps<DashboardBarDatum>) => (
    <ChartTooltip
      color={color}
      content={getTooltipContent(option, String(id), value)}
    />
  );
  const pieTooltip = ({ datum }: PieTooltipProps<DashboardPieDatum>) => (
    <ChartTooltip
      color={datum.color}
      content={getTooltipContent(option, String(datum.label), datum.value)}
    />
  );

  useEffect(() => {
    if (!hasData) {
      setCanRenderChart(false);
      return undefined;
    }

    let secondFrame: number | undefined;
    let timer: number | undefined;
    const firstFrame = window.requestAnimationFrame(() => {
      secondFrame = window.requestAnimationFrame(() => {
        timer = window.setTimeout(
          () => setCanRenderChart(true),
          renderPriority * chartRenderStaggerMs,
        );
      });
    });

    return () => {
      window.cancelAnimationFrame(firstFrame);
      if (secondFrame !== undefined) window.cancelAnimationFrame(secondFrame);
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [hasData, renderPriority]);

  return (
    <Card
      className="dashboard-chart-card"
      data-size={size}
    >
      <div className="dashboard-chart-title-row">
        <div className="dashboard-chart-title">{title}</div>
      </div>
      <div className="dashboard-chart-frame">
        {isLoading && hasData && canRenderChart ? (
          <div
            className="dashboard-chart-mount-loading"
            aria-label={t("dashboard.charts.loading")}
            role="status"
          >
            <Spinner size={18} />
          </div>
        ) : null}
        {shouldShowLoadingState ? (
          <div
            key="loading"
            className="dashboard-chart-empty-state"
            data-size={size}
            aria-label={t("dashboard.charts.loading")}
            role="status"
          >
            <Spinner size={18} />
          </div>
        ) : shouldShowEmptyState ? (
          <div
            key="empty"
            className="dashboard-chart-empty-state"
            data-size={size}
          >
            {t("dashboard.charts.empty")}
          </div>
        ) : canRenderChart ? (
          <div
            key="chart"
            className="dashboard-chart"
            data-ready="true"
            data-size={size}
          >
            <div className="dashboard-chart-plot">
              {option.kind === "line" ? (
                <ResponsiveLine
                  data={option.data}
                  theme={dashboardChartTextTheme}
                  colors={dashboardChartLegendColors}
                  margin={{ top: 24, right: 18, bottom: 34, left: 52 }}
                  xScale={{ type: "point" }}
                  yScale={{
                    type: "linear",
                    min: "auto",
                    max: "auto",
                    stacked: false,
                    reverse: false,
                  }}
                  axisTop={null}
                  axisRight={null}
                  axisBottom={{ tickSize: 0, tickPadding: 8, format: xAxisFormat }}
                  axisLeft={{
                    tickSize: 0,
                    tickPadding: 8,
                    tickValues: yTickValues,
                    format: valueFormat,
                  }}
                  curve="monotoneX"
                  lineWidth={2}
                  enableArea={Boolean(option.enableArea)}
                  areaBaselineValue={areaBaselineValue}
                  areaOpacity={0.14}
                  enablePoints={false}
                  enableGridX={false}
                  enableSlices="x"
                  useMesh={false}
                  sliceTooltip={lineTooltip}
                  yFormat={valueFormat}
                  legends={[]}
                />
              ) : null}
              {option.kind === "bar" ? (
                <ResponsiveBar
                  data={option.data}
                  theme={dashboardChartTextTheme}
                  colors={dashboardChartLegendColors}
                  keys={option.keys}
                  indexBy="label"
                  margin={{ top: 20, right: 18, bottom: 34, left: 56 }}
                  padding={0.28}
                  groupMode={option.groupMode ?? "grouped"}
                  valueScale={{ type: "linear" }}
                  indexScale={{ type: "band", round: true }}
                  borderRadius={5}
                  borderWidth={0}
                  axisTop={null}
                  axisRight={null}
                  axisBottom={{ tickSize: 0, tickPadding: 8, format: xAxisFormat }}
                  axisLeft={{
                    tickSize: 0,
                    tickPadding: 8,
                    tickValues: yTickValues,
                    format: valueFormat,
                  }}
                  enableGridX={false}
                  enableLabel={false}
                  tooltip={barTooltip}
                  valueFormat={valueFormat}
                  legends={[]}
                />
              ) : null}
              {option.kind === "pie" ? (
                <ResponsivePie
                  data={option.data}
                  theme={dashboardChartTextTheme}
                  colors={dashboardChartLegendColors}
                  margin={{ top: 10, right: 12, bottom: 18, left: 12 }}
                  innerRadius={0.58}
                  padAngle={1.5}
                  cornerRadius={4}
                  activeOuterRadiusOffset={6}
                  enableArcLabels
                  enableArcLinkLabels={false}
                  arcLabel={(item) => String(item.label)}
                  arcLabelsSkipAngle={16}
                  tooltip={pieTooltip}
                  valueFormat={valueFormat}
                  legends={[]}
                />
              ) : null}
            </div>
            {option.kind === "line" && option.data.length > 1 ? (
              <ChartLegend
                items={option.data.map((series, index) => ({
                  color: dashboardChartLegendColors[index % dashboardChartLegendColors.length],
                  label: series.id,
                }))}
              />
            ) : null}
            {option.kind === "bar" && option.keys.length > 1 ? (
              <ChartLegend
                items={option.keys.map((key, index) => ({
                  color: dashboardChartLegendColors[index % dashboardChartLegendColors.length],
                  label: key,
                }))}
              />
            ) : null}
            {option.kind === "pie" ? (
              <ChartLegend
                items={option.data.map((item, index) => ({
                  color: dashboardChartLegendColors[index % dashboardChartLegendColors.length],
                  label: item.label,
                }))}
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}
