import { Card, IconButton, TextField } from "@radix-ui/themes";
import { ListRestart } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getCategoryLabel, getStatusLabel } from "../lib/dashboard-formatters";
import type { DashboardQueryParams } from "../lib/dashboard.types";
import { DashboardDatePicker } from "./dashboard-date-picker";
import { DashboardSelectFilter } from "./dashboard-select-filter";

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
    categories: string[];
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

  const resetButton = (
    <div className="dashboard-filter-actions dashboard-filter-actions-inline">
      <IconButton
        aria-label={t("dashboard.filters.reset")}
        color="gray"
        variant="soft"
        onClick={resetFilters}
      >
        <ListRestart size={16} />
      </IconButton>
    </div>
  );

  if (activeTab === "records") {
    return (
      <Card className="dashboard-filter-card">
        <div className="dashboard-filter-scroll">
          <div className="dashboard-filter-records-layout">
            <div className="dashboard-filter-records-row dashboard-filter-records-row-primary">
              <label className="dashboard-filter-field dashboard-filter-field-project">
                <span className="dashboard-filter-label">{t("dashboard.filters.project")}</span>
                <DashboardSelectFilter
                  value={query.projectId}
                  placeholder={t("dashboard.filters.allProjects")}
                  options={options?.projectOptions ?? options?.projectIds ?? []}
                  onChange={(projectId) => updateQuery({ projectId })}
                />
              </label>
              <label className="dashboard-filter-field">
                <span className="dashboard-filter-label">{t("dashboard.filters.model")}</span>
                <DashboardSelectFilter
                  value={query.modelId}
                  placeholder={t("dashboard.filters.allModels")}
                  options={options?.modelOptions ?? options?.modelIds ?? []}
                  onChange={(modelId) => updateQuery({ modelId })}
                />
              </label>
              <label className="dashboard-filter-field">
                <span className="dashboard-filter-label">{t("dashboard.filters.provider")}</span>
                <DashboardSelectFilter
                  value={query.modelProvider}
                  placeholder={t("dashboard.filters.allProviders")}
                  options={options?.modelProviders ?? []}
                  onChange={(modelProvider) => updateQuery({ modelProvider })}
                />
              </label>
              <label className="dashboard-filter-field">
                <span className="dashboard-filter-label">{t("dashboard.filters.category")}</span>
                <DashboardSelectFilter
                  value={query.category}
                  placeholder={t("dashboard.filters.allCategories")}
                  options={options?.categories ?? []}
                  onChange={(category) => updateQuery({ category })}
                  labelForValue={getCategoryLabel}
                />
              </label>
              <label className="dashboard-filter-field">
                <span className="dashboard-filter-label">{t("dashboard.filters.status")}</span>
                <DashboardSelectFilter
                  value={query.status}
                  placeholder={t("dashboard.filters.allStatuses")}
                  options={options?.statuses ?? []}
                  onChange={(status) => updateQuery({ status })}
                  labelForValue={getStatusLabel}
                />
              </label>
            </div>
            <div className="dashboard-filter-records-row dashboard-filter-records-row-secondary">
              <label className="dashboard-filter-field dashboard-filter-field-date">
                <span className="dashboard-filter-label">{t("dashboard.filters.startDate")}</span>
                <DashboardDatePicker
                  value={startDate}
                  placeholder={t("dashboard.filters.startDatePlaceholder")}
                  onChange={setStartDate}
                />
              </label>
              <label className="dashboard-filter-field dashboard-filter-field-date">
                <span className="dashboard-filter-label">{t("dashboard.filters.endDate")}</span>
                <DashboardDatePicker
                  value={endDate}
                  placeholder={t("dashboard.filters.endDatePlaceholder")}
                  onChange={setEndDate}
                />
              </label>
              <label className="dashboard-filter-field dashboard-filter-field-search">
                <span className="dashboard-filter-label">{t("dashboard.filters.search")}</span>
                <TextField.Root
                  value={searchInput}
                  placeholder={t("dashboard.filters.searchPlaceholder")}
                  onChange={(event) => setSearchInput(event.target.value)}
                />
              </label>
              <div className="dashboard-filter-records-reset">{resetButton}</div>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  if (activeTab === "writing") {
    return (
      <Card className="dashboard-filter-card">
        <div className="dashboard-filter-writing-layout">
          <div className="dashboard-filter-writing-project-row">
            <label className="dashboard-filter-field dashboard-filter-field-project">
              <span className="dashboard-filter-label">{t("dashboard.filters.project")}</span>
              <DashboardSelectFilter
                value={query.projectId}
                placeholder={t("dashboard.filters.allProjects")}
                options={options?.projectOptions ?? options?.projectIds ?? []}
                onChange={(projectId) => updateQuery({ projectId })}
              />
            </label>
            <div className="dashboard-filter-writing-reset dashboard-filter-writing-reset-mobile">
              {resetButton}
            </div>
          </div>
          <div className="dashboard-filter-writing-date-row">
            <label className="dashboard-filter-field dashboard-filter-field-date">
              <span className="dashboard-filter-label">{t("dashboard.filters.startDate")}</span>
              <DashboardDatePicker
                value={startDate}
                placeholder={t("dashboard.filters.startDatePlaceholder")}
                onChange={setStartDate}
              />
            </label>
            <label className="dashboard-filter-field dashboard-filter-field-date">
              <span className="dashboard-filter-label">{t("dashboard.filters.endDate")}</span>
              <DashboardDatePicker
                value={endDate}
                placeholder={t("dashboard.filters.endDatePlaceholder")}
                onChange={setEndDate}
              />
            </label>
            <div className="dashboard-filter-writing-reset dashboard-filter-writing-reset-desktop">
              {resetButton}
            </div>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="dashboard-filter-card">
      <div
        className="dashboard-filter-row"
        data-tab={activeTab}
      >
        <div className="dashboard-filter-project-group">
          <label className="dashboard-filter-field dashboard-filter-field-project">
            <span className="dashboard-filter-label">{t("dashboard.filters.project")}</span>
            <DashboardSelectFilter
              value={query.projectId}
              placeholder={t("dashboard.filters.allProjects")}
              options={options?.projectOptions ?? options?.projectIds ?? []}
              onChange={(projectId) => updateQuery({ projectId })}
            />
          </label>
          {resetButton}
        </div>
        <>
          <label className="dashboard-filter-field">
            <span className="dashboard-filter-label">{t("dashboard.filters.model")}</span>
            <DashboardSelectFilter
              value={query.modelId}
              placeholder={t("dashboard.filters.allModels")}
              options={options?.modelOptions ?? options?.modelIds ?? []}
              onChange={(modelId) => updateQuery({ modelId })}
            />
          </label>
          <label className="dashboard-filter-field">
            <span className="dashboard-filter-label">{t("dashboard.filters.provider")}</span>
            <DashboardSelectFilter
              value={query.modelProvider}
              placeholder={t("dashboard.filters.allProviders")}
              options={options?.modelProviders ?? []}
              onChange={(modelProvider) => updateQuery({ modelProvider })}
            />
          </label>
          <label className="dashboard-filter-field">
            <span className="dashboard-filter-label">{t("dashboard.filters.category")}</span>
            <DashboardSelectFilter
              value={query.category}
              placeholder={t("dashboard.filters.allCategories")}
              options={options?.categories ?? []}
              onChange={(category) => updateQuery({ category })}
              labelForValue={getCategoryLabel}
            />
          </label>
          <label className="dashboard-filter-field">
            <span className="dashboard-filter-label">{t("dashboard.filters.status")}</span>
            <DashboardSelectFilter
              value={query.status}
              placeholder={t("dashboard.filters.allStatuses")}
              options={options?.statuses ?? []}
              onChange={(status) => updateQuery({ status })}
              labelForValue={getStatusLabel}
            />
          </label>
        </>
        <label className="dashboard-filter-field dashboard-filter-field-date">
          <span className="dashboard-filter-label">{t("dashboard.filters.startDate")}</span>
          <DashboardDatePicker
            value={startDate}
            placeholder={t("dashboard.filters.startDatePlaceholder")}
            onChange={setStartDate}
          />
        </label>
        <label className="dashboard-filter-field dashboard-filter-field-date">
          <span className="dashboard-filter-label">{t("dashboard.filters.endDate")}</span>
          <DashboardDatePicker
            value={endDate}
            placeholder={t("dashboard.filters.endDatePlaceholder")}
            onChange={setEndDate}
          />
        </label>
      </div>
    </Card>
  );
}
