import NumberFlow from "@number-flow/react";
import { type ReactNode, useMemo } from "react";
import { Card } from "@radix-ui/themes";
import { Flame } from "lucide-react";
import { ActivityCalendar } from "react-activity-calendar";
import { useTranslation } from "react-i18next";
import "react-activity-calendar/tooltips.css";
import { ChartPanel } from "./chart-panel";
import { MetricCard } from "./metric-card";
import {
  buildWritingCumulativeOption,
  buildWritingSourceOption,
  buildWritingTrendOption,
  buildWritingWeekdayOption,
} from "../lib/dashboard-chart-options";
import type { WritingActivityTimeSeriesPoint, WritingDashboardResponse } from "../lib/dashboard.types";

interface WritingDashboardTabProps {
  heroData: WritingDashboardResponse | undefined;
  yearsData: WritingDashboardResponse | undefined;
  detailData: WritingDashboardResponse | undefined;
  isDetailLoading: boolean;
  selectedYear: number;
  onSelectedYearChange: (value: number) => void;
  themeMode: "light" | "dark";
  filtersSlot?: ReactNode;
}

interface CalendarItem {
  date: string;
  count: number;
  level: number;
}

function getCurrentYear(): number {
  return new Date().getFullYear();
}

function formatLocalDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getCreativeWords(point: WritingActivityTimeSeriesPoint): number {
  return Math.max(0, point.userWordDelta + point.agentWordDelta);
}

function getActivityLevel(value: number): number {
  if (value <= 0) return 0;
  if (value >= 8000) return 4;
  if (value >= 4000) return 3;
  if (value >= 2000) return 2;
  return 1;
}

function buildYearCalendarData(points: WritingActivityTimeSeriesPoint[], year: number): CalendarItem[] {
  const start = `${year}-01-01`;
  const end = `${year}-12-31`;
  const yearPoints = points.filter((point) => point.date.startsWith(`${year}-`));
  const dailyWords = new Map(yearPoints.map((point) => [point.date, getCreativeWords(point)]));
  const items = yearPoints.map((point) => {
    const count = getCreativeWords(point);
    return { date: point.date, count, level: getActivityLevel(count) };
  });
  return [
    { date: start, count: dailyWords.get(start) ?? 0, level: getActivityLevel(dailyWords.get(start) ?? 0) },
    ...items.filter((item) => item.date !== start && item.date !== end),
    { date: end, count: dailyWords.get(end) ?? 0, level: getActivityLevel(dailyWords.get(end) ?? 0) },
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
  themeMode,
  filtersSlot,
}: WritingDashboardTabProps) {
  const { t } = useTranslation();
  const isHeroLoading = !heroData;
  const isMetricLoading = isHeroLoading;
  const availableYears = useMemo(() => getCreativeYears(yearsData), [yearsData]);
  const calendarData = useMemo(() => buildYearCalendarData(heroData?.timeSeries ?? [], selectedYear), [heroData?.timeSeries, selectedYear]);
  const writingTrendOption = useMemo(() => buildWritingTrendOption(detailData?.timeSeries ?? []), [detailData?.timeSeries]);
  const writingCumulativeOption = useMemo(() => buildWritingCumulativeOption(detailData?.timeSeries ?? []), [detailData?.timeSeries]);
  const writingSourceOption = useMemo(() => buildWritingSourceOption(detailData?.timeSeries ?? []), [detailData?.timeSeries]);
  const writingWeekdayOption = useMemo(() => buildWritingWeekdayOption(detailData?.timeSeries ?? []), [detailData?.timeSeries]);
  const activeDays = calendarData.filter((item) => item.count > 0).length;
  const streakDays = getStreakDays(calendarData, selectedYear);
  const createdWords = calendarData.reduce((total, item) => total + item.count, 0);
  const creativeChapters = heroData?.summary.creativeChapters ?? 0;

  return (
    <section className="dashboard-tab-panel">
      <section className="dashboard-writing-hero dashboard-writing-hero-yearly">
        <Card className="dashboard-activity-card dashboard-writing-calendar-card">
          <div className="dashboard-year-card-layout">
            <aside className="dashboard-year-selector" aria-label={t("dashboard.charts.yearSelector")}>
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
                <NumberFlow value={selectedYear} locales="zh-CN" format={{ maximumFractionDigits: 0 }} className="dashboard-number-flow dashboard-number-flow-inline" />
                {" "}
                {t("dashboard.charts.yearSummaryMiddle")}
                {" "}
                <NumberFlow value={activeDays} locales="zh-CN" format={{ maximumFractionDigits: 0 }} className="dashboard-number-flow dashboard-number-flow-inline" />
                {t("dashboard.charts.yearSummarySuffix")}
              </div>
              <div className="dashboard-calendar-frame dashboard-calendar-frame-yearly">
                <ActivityCalendar
                  data={calendarData}
                  blockSize={12}
                  blockRadius={3}
                  blockMargin={4}
                  fontSize={12}
                  weekStart={1}
                  colorScheme="light"
                  showWeekdayLabels
                  theme={{
                    light: ["var(--gray-a3)", "#b7dbc2", "#7fbd94", "#4f9467", "#2f6848"],
                    dark: ["var(--gray-a3)", "#b7dbc2", "#7fbd94", "#4f9467", "#2f6848"],
                  }}
                  labels={{ totalCount: t("dashboard.charts.tooltipWords", { count: "{{count}}" }) }}
                  tooltips={{
                    activity: {
                      text: ({ count, date }) => count > 0
                        ? t("dashboard.charts.tooltipActivity", { date, count })
                        : t("dashboard.charts.tooltipNoActivity", { date }),
                    },
                  }}
                />
              </div>
            </div>
          </div>
        </Card>

        <section className="dashboard-writing-stack" aria-label={t("dashboard.charts.annualStats")}>
          <MetricCard label={t("dashboard.charts.totalDays")} value={activeDays} valueFormat={{ maximumFractionDigits: 0 }} isLoading={isMetricLoading} hasValue={Boolean(heroData)} cardClassName="dashboard-writing-stat-card" />
          <MetricCard label={t("dashboard.charts.streakDays")} value={streakDays} valueFormat={{ maximumFractionDigits: 0 }} isLoading={isMetricLoading} hasValue={Boolean(heroData)} cardClassName="dashboard-writing-stat-card" valueClassName="dashboard-streak-value" prefix={streakDays > 0 ? <Flame size={20} className="dashboard-streak-icon" /> : null} />
          <MetricCard label={t("dashboard.charts.totalChapters")} value={creativeChapters} valueFormat={{ maximumFractionDigits: 0 }} isLoading={isMetricLoading} hasValue={Boolean(heroData)} cardClassName="dashboard-writing-stat-card" />
          <MetricCard label={t("dashboard.charts.totalWords")} value={createdWords} valueFormat={{ maximumFractionDigits: 0 }} isLoading={isMetricLoading} hasValue={Boolean(heroData)} cardClassName="dashboard-writing-stat-card" />
        </section>
      </section>

      {filtersSlot}

      <section className="dashboard-writing-layout dashboard-chart-grid dashboard-chart-grid-balanced">
        <ChartPanel title={t("dashboard.charts.writingTrend")} option={writingTrendOption} isLoading={isDetailLoading} themeMode={themeMode} size="wide" />
        <ChartPanel title={t("dashboard.charts.cumulativeWords")} option={writingCumulativeOption} isLoading={isDetailLoading} themeMode={themeMode} size="wide" />
        <ChartPanel title={t("dashboard.charts.sourceContribution")} option={writingSourceOption} isLoading={isDetailLoading} themeMode={themeMode} size="medium" />
        <ChartPanel title={t("dashboard.charts.activeWeekday")} option={writingWeekdayOption} isLoading={isDetailLoading} themeMode={themeMode} size="medium" />
      </section>
    </section>
  );
}
