import { Card, IconButton, TextField } from "@radix-ui/themes";
import { ListRestart } from "lucide-react";
import { useTranslation } from "react-i18next";
import { DashboardDatePicker } from "./dashboard-date-picker";
import { DashboardSelectFilter } from "./dashboard-select-filter";
import { getAgentLabel, getStatusLabel } from "../lib/dashboard-formatters";
import type { DashboardQueryParams } from "../lib/dashboard.types";

type DashboardTab = "writing" | "llm" | "records";

interface DashboardFiltersProps {
  activeTab: DashboardTab;
  query: DashboardQueryParams;
  options?: {
    projectIds: string[];
    projectOptions: Array<{ value: string; label: string }>;
    modelProviders: string[];
    modelIds: string[];
    modelOptions: Array<{ value: string; label: string }>;
    agentNodes: string[];
    statuses: string[];
  };
  searchInput: string;
  startDate: string;
  endDate: string;
  updateQuery: (updates: Partial<DashboardQueryParams>) => void;
  setSearchInput: (value: string) => void;
  setStartDate: (value: string) => void;
  setEndDate: (value: string) => void;
  resetFilters: () => void;
}

export function DashboardFilters({
  activeTab,
  query,
  options,
  searchInput,
  startDate,
  endDate,
  updateQuery,
  setSearchInput,
  setStartDate,
  setEndDate,
  resetFilters,
}: DashboardFiltersProps) {
  const { t } = useTranslation();

  return (
    <Card className="dashboard-filter-card">
      <div className="dashboard-filter-row" data-tab={activeTab}>
        <label className="dashboard-filter-field dashboard-filter-field-project">
          <span className="dashboard-filter-label">{t("dashboard.filters.project")}</span>
          <DashboardSelectFilter
            value={query.projectId}
            placeholder={t("dashboard.filters.allProjects")}
            options={options?.projectOptions ?? options?.projectIds ?? []}
            onChange={(projectId) => updateQuery({ projectId })}
          />
        </label>
        {activeTab !== "writing" ? (
          <>
            <label className="dashboard-filter-field">
              <span className="dashboard-filter-label">{t("dashboard.filters.model")}</span>
              <DashboardSelectFilter value={query.modelId} placeholder={t("dashboard.filters.allModels")} options={options?.modelOptions ?? options?.modelIds ?? []} onChange={(modelId) => updateQuery({ modelId })} />
            </label>
            <label className="dashboard-filter-field">
              <span className="dashboard-filter-label">{t("dashboard.filters.provider")}</span>
              <DashboardSelectFilter value={query.modelProvider} placeholder={t("dashboard.filters.allProviders")} options={options?.modelProviders ?? []} onChange={(modelProvider) => updateQuery({ modelProvider })} />
            </label>
            {activeTab === "llm" || activeTab === "records" ? (
              <label className="dashboard-filter-field">
                <span className="dashboard-filter-label">{t("dashboard.filters.agent")}</span>
                <DashboardSelectFilter value={query.agentNode} placeholder={t("dashboard.filters.allRoles")} options={options?.agentNodes ?? []} onChange={(agentNode) => updateQuery({ agentNode })} labelForValue={getAgentLabel} />
              </label>
            ) : null}
            <label className="dashboard-filter-field">
              <span className="dashboard-filter-label">{t("dashboard.filters.status")}</span>
              <DashboardSelectFilter value={query.status} placeholder={t("dashboard.filters.allStatuses")} options={options?.statuses ?? []} onChange={(status) => updateQuery({ status })} labelForValue={getStatusLabel} />
            </label>
          </>
        ) : null}
        <label className="dashboard-filter-field dashboard-filter-field-date">
          <span className="dashboard-filter-label">{t("dashboard.filters.startDate")}</span>
          <DashboardDatePicker value={startDate} placeholder={t("dashboard.filters.startDatePlaceholder")} onChange={setStartDate} />
        </label>
        <label className="dashboard-filter-field dashboard-filter-field-date">
          <span className="dashboard-filter-label">{t("dashboard.filters.endDate")}</span>
          <DashboardDatePicker value={endDate} placeholder={t("dashboard.filters.endDatePlaceholder")} onChange={setEndDate} />
        </label>
        {activeTab === "records" ? (
          <label className="dashboard-filter-field dashboard-filter-field-search">
            <span className="dashboard-filter-label">{t("dashboard.filters.search")}</span>
            <TextField.Root value={searchInput} placeholder={t("dashboard.filters.searchPlaceholder")} onChange={(event) => setSearchInput(event.target.value)} />
          </label>
        ) : null}
        <div className="dashboard-filter-actions">
          <IconButton aria-label={t("dashboard.filters.reset")} color="gray" variant="soft" onClick={resetFilters}>
            <ListRestart size={16} />
          </IconButton>
        </div>
      </div>
    </Card>
  );
}
