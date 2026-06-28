import { useEffect, useMemo, useState } from "react";
import { Box } from "@radix-ui/themes";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { BarChart3, BookOpenText, ListTree } from "lucide-react";
import { MobileAppSidebarTrigger } from "@/features/app-shell";
import { DashboardFilters } from "../components/dashboard-filters";
import { DashboardRecordsTab } from "../components/dashboard-records-tab";
import { LlmDashboardTab } from "../components/llm-dashboard-tab";
import { WritingDashboardTab } from "../components/writing-dashboard-tab";
import { fetchLlmDashboardRecords, fetchLlmDashboardStats, fetchWritingDashboard } from "../lib/dashboard-api";
import { toIsoDateTime } from "../lib/dashboard-formatters";
import type { DashboardQueryParams, WritingDashboardQueryParams } from "../lib/dashboard.types";
import "./dashboard-page.css";

type DashboardTab = "writing" | "llm" | "records";

const defaultLlmQuery: DashboardQueryParams = {
  page: 1,
  pageSize: 20,
  sortBy: "created_at",
  sortOrder: "desc",
};

const tabs: Array<{ value: DashboardTab; label: string; icon: typeof BookOpenText }> = [
  { value: "writing", label: "写作", icon: BookOpenText },
  { value: "llm", label: "LLM 统计", icon: BarChart3 },
  { value: "records", label: "调用记录", icon: ListTree },
];

function getCurrentYear(): number {
  return new Date().getFullYear();
}

function getYearStart(year: number): string {
  return `${year}-01-01`;
}

function getYearEnd(year: number): string {
  return `${year}-12-31`;
}

function getUserTimezone(): string | undefined {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

interface DashboardPageProps {
  appearance: "light" | "dark";
}

export function DashboardPage({ appearance }: DashboardPageProps) {
  const [activeTab, setActiveTab] = useState<DashboardTab>("writing");
  const [llmQuery, setLlmQuery] = useState<DashboardQueryParams>(defaultLlmQuery);
  const [searchInput, setSearchInput] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [writingYear, setWritingYear] = useState(getCurrentYear);
  const isWritingTab = activeTab === "writing";
  const isLlmTab = activeTab === "llm";
  const isRecordsTab = activeTab === "records";

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const nextSearch = searchInput || undefined;
      setLlmQuery((current) => {
        if (current.search === nextSearch) return current;
        return { ...current, search: nextSearch, page: 1 };
      });
    }, 300);

    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const startAt = toIsoDateTime(startDate, "start");
  const endAt = toIsoDateTime(endDate, "end");
  const userTimezone = getUserTimezone();

  const llmDashboardQuery = useMemo(
    () => ({ ...llmQuery, startAt, endAt }),
    [endAt, llmQuery, startAt]
  );

  const writingHeroQuery = useMemo<WritingDashboardQueryParams>(
    () => ({
      startAt: toIsoDateTime(getYearStart(writingYear), "start"),
      endAt: toIsoDateTime(getYearEnd(writingYear), "end"),
      timezone: userTimezone,
    }),
    [userTimezone, writingYear]
  );

  const writingYearsQuery = useMemo<WritingDashboardQueryParams>(() => ({ timezone: userTimezone }), [userTimezone]);

  const writingDetailQuery = useMemo<WritingDashboardQueryParams>(
    () => ({ projectId: llmQuery.projectId, startAt, endAt, timezone: userTimezone }),
    [endAt, llmQuery.projectId, startAt, userTimezone]
  );

  const { data: llmStatsData, isFetching: isLlmStatsFetching } = useQuery({
    queryKey: ["dashboard", "llm-api", "stats", llmDashboardQuery],
    queryFn: () => fetchLlmDashboardStats(llmDashboardQuery),
    enabled: isLlmTab,
    placeholderData: keepPreviousData,
  });

  const { data: llmRecordsData, isFetching: isLlmRecordsFetching } = useQuery({
    queryKey: ["dashboard", "llm-api", "records", llmDashboardQuery],
    queryFn: () => fetchLlmDashboardRecords(llmDashboardQuery),
    enabled: isRecordsTab,
    placeholderData: keepPreviousData,
  });

  const { data: writingHeroData } = useQuery({
    queryKey: ["dashboard", "writing", "hero", writingHeroQuery],
    queryFn: () => fetchWritingDashboard(writingHeroQuery),
    enabled: isWritingTab,
  });

  const { data: writingYearsData } = useQuery({
    queryKey: ["dashboard", "writing", "years", writingYearsQuery],
    queryFn: () => fetchWritingDashboard(writingYearsQuery),
    enabled: isWritingTab,
  });

  const { data: writingDetailData, isFetching: isWritingDetailFetching } = useQuery({
    queryKey: ["dashboard", "writing", "detail", writingDetailQuery],
    queryFn: () => fetchWritingDashboard(writingDetailQuery),
    enabled: isWritingTab,
  });

  const llmOptions = isRecordsTab ? llmRecordsData?.options : llmStatsData?.options;
  const totalPages = Math.max(1, Math.ceil((llmRecordsData?.records.total ?? 0) / llmQuery.pageSize));

  const updateLlmQuery = (updates: Partial<DashboardQueryParams>) => {
    setLlmQuery((current) => ({ ...current, ...updates, page: updates.page ?? 1 }));
  };

  const resetFilters = () => {
    setSearchInput("");
    setStartDate("");
    setEndDate("");
    setWritingYear(getCurrentYear());
    setLlmQuery(defaultLlmQuery);
  };

  const filters = (
    <DashboardFilters
      activeTab={activeTab}
      query={llmQuery}
      options={llmOptions}
      searchInput={searchInput}
      startDate={startDate}
      endDate={endDate}
      updateQuery={updateLlmQuery}
      setSearchInput={setSearchInput}
      setStartDate={setStartDate}
      setEndDate={setEndDate}
      resetFilters={resetFilters}
    />
  );

  return (
    <Box className="dashboard-page">
      <div className="dashboard-shell">
        <header className="dashboard-header">
          <div className="dashboard-title-block" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <MobileAppSidebarTrigger />
            <h1 className="dashboard-title">仪表盘</h1>
          </div>
        </header>

        <nav className="dashboard-tab-nav" role="tablist" aria-label="仪表盘分区">
          {tabs.map((tab) => {
            const TabIcon = tab.icon;
            return (
              <button
                key={tab.value}
                type="button"
                className="dashboard-tab-button"
                data-active={activeTab === tab.value}
                role="tab"
                aria-selected={activeTab === tab.value}
                onClick={() => setActiveTab(tab.value)}
              >
                <TabIcon size={16} className="dashboard-tab-icon" aria-hidden="true" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {isWritingTab ? (
          <WritingDashboardTab
            heroData={writingHeroData}
            yearsData={writingYearsData}
            detailData={writingDetailData}
            isDetailLoading={isWritingDetailFetching}
            selectedYear={writingYear}
            onSelectedYearChange={setWritingYear}
            themeMode={appearance}
            filtersSlot={filters}
          />
        ) : null}
        {isLlmTab ? <LlmDashboardTab data={llmStatsData} isLoading={isLlmStatsFetching} themeMode={appearance} /> : null}
        {isRecordsTab ? (
          <>
            {filters}
            <DashboardRecordsTab
              data={llmRecordsData}
              query={llmQuery}
              totalPages={totalPages}
              isLoading={isLlmRecordsFetching}
              updateQuery={updateLlmQuery}
            />
          </>
        ) : null}

      </div>
    </Box>
  );
}
