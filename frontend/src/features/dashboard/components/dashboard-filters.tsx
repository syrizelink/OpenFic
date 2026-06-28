import { Card, IconButton, TextField } from "@radix-ui/themes";
import { ListRestart } from "lucide-react";
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
  return (
    <Card className="dashboard-filter-card">
      <div className="dashboard-filter-row" data-tab={activeTab}>
        <label className="dashboard-filter-field dashboard-filter-field-project">
          <span className="dashboard-filter-label">项目</span>
          <DashboardSelectFilter
            value={query.projectId}
            placeholder="全部项目"
            options={options?.projectOptions ?? options?.projectIds ?? []}
            onChange={(projectId) => updateQuery({ projectId })}
          />
        </label>
        {activeTab !== "writing" ? (
          <>
            <label className="dashboard-filter-field">
              <span className="dashboard-filter-label">模型</span>
              <DashboardSelectFilter value={query.modelId} placeholder="全部模型" options={options?.modelOptions ?? options?.modelIds ?? []} onChange={(modelId) => updateQuery({ modelId })} />
            </label>
            <label className="dashboard-filter-field">
              <span className="dashboard-filter-label">提供商</span>
              <DashboardSelectFilter value={query.modelProvider} placeholder="全部提供商" options={options?.modelProviders ?? []} onChange={(modelProvider) => updateQuery({ modelProvider })} />
            </label>
            {activeTab === "llm" || activeTab === "records" ? (
              <label className="dashboard-filter-field">
                <span className="dashboard-filter-label">Agent</span>
                <DashboardSelectFilter value={query.agentNode} placeholder="全部角色" options={options?.agentNodes ?? []} onChange={(agentNode) => updateQuery({ agentNode })} labelForValue={getAgentLabel} />
              </label>
            ) : null}
            <label className="dashboard-filter-field">
              <span className="dashboard-filter-label">状态</span>
              <DashboardSelectFilter value={query.status} placeholder="全部状态" options={options?.statuses ?? []} onChange={(status) => updateQuery({ status })} labelForValue={getStatusLabel} />
            </label>
          </>
        ) : null}
        <label className="dashboard-filter-field dashboard-filter-field-date">
          <span className="dashboard-filter-label">开始日期</span>
          <DashboardDatePicker value={startDate} placeholder="选择开始日期" onChange={setStartDate} />
        </label>
        <label className="dashboard-filter-field dashboard-filter-field-date">
          <span className="dashboard-filter-label">结束日期</span>
          <DashboardDatePicker value={endDate} placeholder="选择结束日期" onChange={setEndDate} />
        </label>
        {activeTab === "records" ? (
          <label className="dashboard-filter-field dashboard-filter-field-search">
            <span className="dashboard-filter-label">搜索</span>
            <TextField.Root value={searchInput} placeholder="搜索模型、Agent 或错误信息" onChange={(event) => setSearchInput(event.target.value)} />
          </label>
        ) : null}
        <div className="dashboard-filter-actions">
          <IconButton aria-label="重置筛选" color="gray" variant="soft" onClick={resetFilters}>
            <ListRestart size={16} />
          </IconButton>
        </div>
      </div>
    </Card>
  );
}
