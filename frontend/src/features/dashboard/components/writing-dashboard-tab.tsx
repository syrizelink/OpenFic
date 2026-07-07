import { ResponsiveTimeRange, type CalendarTooltipProps } from "@nivo/calendar";
import NumberFlow from "@number-flow/react";
import { Card } from "@radix-ui/themes";
import { Flame } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  buildWritingCumulativeOption,
  buildWritingSourceOption,
  buildWritingTrendOption,
  buildWritingWeekdayOption,
} from "../lib/dashboard-chart-options";
import type {
  WritingActivityTimeSeriesPoint,
  WritingDashboardResponse,
} from "../lib/dashboard.types";
import { ChartPanel } from "./chart-panel";
import { MetricCard } from "./metric-card";

interface WritingDashboardTabProps {
  heroData: WritingDashboardResponse | undefined;
  yearsData: WritingDashboardResponse | undefined;
  detailData: WritingDashboardResponse | undefined;
  isDetailLoading: boolean;
  selectedYear: number;
  onSelectedYearChange: (value: number) => void;
  filtersSlot?: ReactNode;
}

interface CalendarItem {
  date: string;
  count: number;
}

interface NivoCalendarDatum {
  day: string;
  value: number;
}

const calendarColors = ["#d9e5dc", "#a9c4b3", "#6f9a7f", "#315f46"];
const dashboardCalendarFontFamily = "var(--app-font-family)";
const dashboardCalendarTextTheme = {
  background: "transparent",
  fontFamily: dashboardCalendarFontFamily,
  axis: {
    domain: { line: { stroke: "var(--gray-a6)" } },
    ticks: {
      line: { stroke: "var(--gray-a6)" },
      text: { fill: "var(--gray-11)", fontFamily: dashboardCalendarFontFamily, fontSize: 13 },
    },
    legend: { text: { fill: "var(--gray-11)", fontFamily: dashboardCalendarFontFamily, fontSize: 13 } },
  },
  grid: { line: { stroke: "var(--gray-a4)" } },
  crosshair: { line: { stroke: "var(--gray-12)", strokeWidth: 1 } },
  legends: { text: { fill: "var(--gray-11)", fontFamily: dashboardCalendarFontFamily, fontSize: 13 } },
  labels: { text: { fill: "var(--gray-12)", fontFamily: dashboardCalendarFontFamily, fontSize: 13 } },
  tooltip: {
    container: {
      borderColor: "var(--gray-a6)",
      background: "var(--color-panel-solid)",
      color: "var(--gray-12)",
      fontFamily: dashboardCalendarFontFamily,
      fontSize: "13px",
    },
  },
};

function getCurrentYear(): number {
  return new Date().getFullYear();
}

function formatLocalDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatCalendarTooltipDate(day: string | Date): string {
  return typeof day === "string" ? day.slice(5) : formatLocalDate(day).slice(5);
}

function getCreativeWords(point: WritingActivityTimeSeriesPoint): number {
  return Math.max(0, point.userWordDelta + point.agentWordDelta);
}

function buildYearCalendarData(
  points: WritingActivityTimeSeriesPoint[],
  year: number,
): CalendarItem[] {
  const start = `${year}-01-01`;
  const end = `${year}-12-31`;
  const yearPoints = points.filter((point) => point.date.startsWith(`${year}-`));
  const dailyWords = new Map(yearPoints.map((point) => [point.date, getCreativeWords(point)]));
  const items = yearPoints.map((point) => {
    const count = getCreativeWords(point);
    return { date: point.date, count };
  });
  return [
    {
      date: start,
      count: dailyWords.get(start) ?? 0,
    },
    ...items.filter((item) => item.date !== start && item.date !== end),
    {
      date: end,
      count: dailyWords.get(end) ?? 0,
    },
  ];
}

function getCreativeYears(data: WritingDashboardResponse | undefined): number[] {
  const years = new Set<number>();
  for (const point of data?.timeSeries ?? []) {
    if (getCreativeWords(point) > 0) years.add(Number(point.date.slice(0, 4)));
  }
  if (years.size === 0) years.add(getCurrentYear());
  return Array.from(years).sort((a, b) => b - a);
}

function getStreakDays(items: CalendarItem[], year: number): number {
  const currentYear = getCurrentYear();
  const dailyCounts = new Map(items.map((item) => [item.date, item.count]));
  const cursor = year >= currentYear ? new Date() : new Date(year, 11, 31);
  let streak = 0;

  while (cursor.getFullYear() === year) {
    if ((dailyCounts.get(formatLocalDate(cursor)) ?? 0) <= 0) break;
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }

  return streak;
}

export function WritingDashboardTab({
  heroData,
  yearsData,
  detailData,
  isDetailLoading,
  selectedYear,
  onSelectedYearChange,
  filtersSlot,
}: WritingDashboardTabProps) {
  const { t } = useTranslation();
  const isHeroLoading = !heroData;
  const isMetricLoading = isHeroLoading;
  const availableYears = useMemo(() => getCreativeYears(yearsData), [yearsData]);
  const calendarData = useMemo(
    () => buildYearCalendarData(heroData?.timeSeries ?? [], selectedYear),
    [heroData?.timeSeries, selectedYear],
  );
  const calendarChartData = useMemo<NivoCalendarDatum[]>(
    () =>
      calendarData
        .filter((item) => item.count > 0)
        .map((item) => ({ day: item.date, value: item.count })),
    [calendarData],
  );
  const [canRenderCalendar, setCanRenderCalendar] = useState(false);

  useEffect(() => {
    setCanRenderCalendar(false);

    let secondFrame: number | undefined;
    const firstFrame = window.requestAnimationFrame(() => {
      secondFrame = window.requestAnimationFrame(() => setCanRenderCalendar(true));
    });

    return () => {
      window.cancelAnimationFrame(firstFrame);
      if (secondFrame !== undefined) window.cancelAnimationFrame(secondFrame);
    };
  }, [calendarChartData, selectedYear]);

  const CalendarTooltip = ({ day, value }: CalendarTooltipProps) => (
    <div className="dashboard-chart-tooltip">
      {t("dashboard.charts.calendarTooltipPrefix", { date: formatCalendarTooltipDate(day) })}{" "}
      <strong className="dashboard-chart-tooltip-value">{Number(value)}</strong>{" "}
      {t("dashboard.charts.calendarTooltipSuffix")}
    </div>
  );
  const writingTrendOption = useMemo(
    () => buildWritingTrendOption(detailData?.timeSeries ?? []),
    [detailData?.timeSeries],
  );
  const writingCumulativeOption = useMemo(
    () => buildWritingCumulativeOption(detailData?.timeSeries ?? []),
    [detailData?.timeSeries],
  );
  const writingSourceOption = useMemo(
    () => buildWritingSourceOption(detailData?.timeSeries ?? []),
    [detailData?.timeSeries],
  );
  const writingWeekdayOption = useMemo(
    () => buildWritingWeekdayOption(detailData?.timeSeries ?? []),
    [detailData?.timeSeries],
  );
  const activeDays = calendarData.filter((item) => item.count > 0).length;
  const streakDays = getStreakDays(calendarData, selectedYear);
  const createdWords = calendarData.reduce((total, item) => total + item.count, 0);
  const creativeChapters = heroData?.summary.creativeChapters ?? 0;

  return (
    <section className="dashboard-tab-panel">
      <section className="dashboard-writing-hero dashboard-writing-hero-yearly">
        <Card className="dashboard-activity-card dashboard-writing-calendar-card">
          <div className="dashboard-year-card-layout">
            <aside
              className="dashboard-year-selector"
              aria-label={t("dashboard.charts.yearSelector")}
            >
              {availableYears.map((year) => (
                <button
                  key={year}
                  type="button"
                  className="dashboard-year-button"
                  data-active={selectedYear === year}
                  onClick={() => onSelectedYearChange(year)}
                >
                  {year}
                </button>
              ))}
            </aside>
            <div className="dashboard-year-calendar-main">
              <div className="dashboard-year-summary">
                <NumberFlow
                  value={selectedYear}
                  locales="zh-CN"
                  format={{ maximumFractionDigits: 0, useGrouping: false }}
                  className="dashboard-number-flow dashboard-number-flow-inline"
                />{" "}
                {t("dashboard.charts.yearSummaryMiddle")}{" "}
                <NumberFlow
                  value={activeDays}
                  locales="zh-CN"
                  format={{ maximumFractionDigits: 0, useGrouping: false }}
                  className="dashboard-number-flow dashboard-number-flow-inline"
                />{" "}
                {t("dashboard.charts.yearSummarySuffix")}
              </div>
              <div className="dashboard-calendar-frame dashboard-calendar-frame-yearly">
                <div className="dashboard-nivo-calendar">
                  <div className="dashboard-nivo-calendar-chart">
                    {canRenderCalendar ? (
                      <ResponsiveTimeRange
                        data={calendarChartData}
                        theme={dashboardCalendarTextTheme}
                        from={`${selectedYear}-01-01`}
                        to={`${selectedYear}-12-31`}
                        firstWeekday="monday"
                        weekdayTicks={[]}
                        weekdayLegendOffset={0}
                        align="top-left"
                        margin={{ top: 24, right: 0, bottom: 0, left: 0 }}
                        dayRadius={2}
                        daySpacing={4}
                        dayBorderWidth={0.5}
                        dayBorderColor="var(--gray-a5)"
                        emptyColor="var(--gray-a3)"
                        colors={calendarColors}
                        minValue={0}
                        maxValue="auto"
                        tooltip={CalendarTooltip}
                      />
                    ) : (
                      <div
                        className="dashboard-nivo-calendar-loading"
                        role="status"
                        aria-label={t("dashboard.charts.loading")}
                      />
                    )}
                  </div>
                  <div className="dashboard-nivo-calendar-footer">
                    <span>
                      {t("dashboard.charts.yearTotalWords", {
                        count: createdWords,
                        year: selectedYear,
                      })}
                    </span>
                    <div className="dashboard-nivo-calendar-legend">
                      <span>{t("dashboard.charts.calendarLess")}</span>
                      <span className="dashboard-nivo-calendar-swatch" />
                      {calendarColors.map((color, index) => (
                        <span
                          key={color}
                          className="dashboard-nivo-calendar-swatch"
                          data-level={index + 1}
                        />
                      ))}
                      <span>{t("dashboard.charts.calendarMore")}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <section
          className="dashboard-writing-stack"
          aria-label={t("dashboard.charts.annualStats")}
        >
          <MetricCard
            label={t("dashboard.charts.totalDays")}
            value={activeDays}
            valueFormat={{ maximumFractionDigits: 0 }}
            isLoading={isMetricLoading}
            hasValue={Boolean(heroData)}
            cardClassName="dashboard-writing-stat-card"
          />
          <MetricCard
            label={t("dashboard.charts.streakDays")}
            value={streakDays}
            valueFormat={{ maximumFractionDigits: 0 }}
            isLoading={isMetricLoading}
            hasValue={Boolean(heroData)}
            cardClassName="dashboard-writing-stat-card"
            valueClassName="dashboard-streak-value"
            prefix={
              streakDays > 0 ? (
                <Flame
                  size={20}
                  className="dashboard-streak-icon"
                />
              ) : null
            }
          />
          <MetricCard
            label={t("dashboard.charts.totalChapters")}
            value={creativeChapters}
            valueFormat={{ maximumFractionDigits: 0 }}
            isLoading={isMetricLoading}
            hasValue={Boolean(heroData)}
            cardClassName="dashboard-writing-stat-card"
          />
          <MetricCard
            label={t("dashboard.charts.totalWords")}
            value={createdWords}
            valueFormat={{ maximumFractionDigits: 0 }}
            isLoading={isMetricLoading}
            hasValue={Boolean(heroData)}
            cardClassName="dashboard-writing-stat-card"
          />
        </section>
      </section>

      {filtersSlot}

      <section className="dashboard-writing-layout dashboard-chart-grid dashboard-chart-grid-balanced">
        <ChartPanel
          title={t("dashboard.charts.writingTrend")}
          option={writingTrendOption}
          isLoading={isDetailLoading}
          size="wide"
          renderPriority={0}
        />
        <ChartPanel
          title={t("dashboard.charts.cumulativeWords")}
          option={writingCumulativeOption}
          isLoading={isDetailLoading}
          size="wide"
          renderPriority={1}
        />
        <ChartPanel
          title={t("dashboard.charts.sourceContribution")}
          option={writingSourceOption}
          isLoading={isDetailLoading}
          size="medium"
          renderPriority={2}
        />
        <ChartPanel
          title={t("dashboard.charts.activeWeekday")}
          option={writingWeekdayOption}
          isLoading={isDetailLoading}
          size="medium"
          renderPriority={3}
        />
      </section>
    </section>
  );
}
