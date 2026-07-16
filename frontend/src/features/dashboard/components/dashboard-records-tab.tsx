import {
  Badge,
  Box,
  Button,
  Card,
  Dialog,
  Flex,
  IconButton,
  ScrollArea,
  Text,
} from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownNarrowWide,
  ArrowUpDown,
  ArrowUpWideNarrow,
  ChevronLeft,
  ChevronRight,
  Info,
  ScanSearch,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { PromptChainDialog, Spinner } from "@/components";
import type { PromptChainDialogEntry } from "@/components";
import { fetchAgentDefinitions } from "@/features/settings/lib/agent-definitions-api";

import { fetchDashboardRecordPrompt } from "../lib/dashboard-api";
import {
  formatDateTime,
  formatNumber,
  formatSeconds,
  getCategoryLabel,
  getOperationLabel,
  getStatusLabel,
} from "../lib/dashboard-formatters";
import type {
  DashboardAuditRecord,
  DashboardQueryParams,
  DashboardRecordsResponse,
  DashboardSortBy,
} from "../lib/dashboard.types";

interface DashboardRecordsTabProps {
  data: DashboardRecordsResponse | undefined;
  query: DashboardQueryParams;
  totalPages: number;
  isLoading: boolean;
  updateQuery: (updates: Partial<DashboardQueryParams>) => void;
}

function parseJson(value: string | null): unknown {
  if (!value) return null;

  try {
    return JSON.parse(value) as unknown;
  } catch {
    return value;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringifyContent(value: unknown): string {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (
      (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
      (trimmed.startsWith("[") && trimmed.endsWith("]"))
    ) {
      try {
        return JSON.stringify(JSON.parse(trimmed), null, 2);
      } catch {
        return value;
      }
    }
    return value;
  }
  if (value === null || value === undefined) return "";
  return JSON.stringify(value, null, 2);
}

function getPromptEntries(requestMessages: string | null | undefined): PromptChainDialogEntry[] {
  const parsed = parseJson(requestMessages ?? null);
  if (!Array.isArray(parsed)) return [];

  return parsed.map((item, index) => {
    if (!isRecord(item)) {
      return {
        role: "unknown",
        content: stringifyContent(item),
        name: `#${index + 1}`,
      };
    }

    const role = typeof item.role === "string" ? item.role : "unknown";
    const content = stringifyContent(item.content);
    const toolCalls =
      Array.isArray(item.tool_calls) && item.tool_calls.length > 0
        ? `\n\nTool calls:\n${JSON.stringify(item.tool_calls, null, 2)}`
        : "";

    return {
      role,
      content: `${content}${toolCalls}`,
      name: `#${index + 1}`,
    };
  });
}

interface ToolCallEntry {
  name: string | null;
  content: string;
}

function getToolCallEntries(value: string | null): ToolCallEntry[] {
  const parsed = parseJson(value);
  if (parsed === null) return [];

  const toolCalls = Array.isArray(parsed) ? parsed : [parsed];
  return toolCalls.map((toolCall) => ({
    name: isRecord(toolCall) && typeof toolCall.name === "string" ? toolCall.name : null,
    content: stringifyContent(toolCall),
  }));
}

function hasErrorDetails(record: DashboardAuditRecord): boolean {
  return Boolean(
    record.errorMessage || record.errorType || typeof record.errorStatusCode === "number",
  );
}

function getStatusColor(status: string): "green" | "red" | "gray" {
  if (status === "success") return "green";
  if (status === "error" || status === "failed" || status === "failure") return "red";
  return "gray";
}

function isFailedRecord(record: DashboardAuditRecord): boolean {
  return record.status === "error" || record.status === "failed" || record.status === "failure";
}

function getRecordDescription(
  record: DashboardAuditRecord | null,
  t: ReturnType<typeof useTranslation>["t"],
): string | undefined {
  if (!record) return undefined;
  const modelName = record.modelName || record.modelId;
  const projectName = record.projectTitle || t("dashboard.records.unknownProject");
  return `${formatDateTime(record.createdAt)} · ${projectName} · ${modelName}`;
}

interface SortableHeaderProps {
  label: string;
  sortBy: DashboardSortBy;
  query: DashboardQueryParams;
  updateQuery: (updates: Partial<DashboardQueryParams>) => void;
}

function SortableHeader({ label, sortBy, query, updateQuery }: SortableHeaderProps) {
  const isActive = query.sortBy === sortBy;
  const SortIcon = !isActive
    ? ArrowUpDown
    : query.sortOrder === "desc"
      ? ArrowDownNarrowWide
      : ArrowUpWideNarrow;

  const handleSort = () => {
    updateQuery({
      sortBy,
      sortOrder: isActive && query.sortOrder === "desc" ? "asc" : "desc",
    });
  };

  return (
    <button
      type="button"
      className="dashboard-record-sort-button"
      data-active={isActive}
      onClick={handleSort}
    >
      <span>{label}</span>
      <SortIcon
        size={14}
        aria-hidden="true"
      />
    </button>
  );
}

function getVisiblePages(currentPage: number, totalPages: number): Array<number | "ellipsis"> {
  if (totalPages <= 6) return Array.from({ length: totalPages }, (_, index) => index + 1);
  if (currentPage <= 3) return [1, 2, 3, "ellipsis", totalPages - 1, totalPages];
  if (currentPage >= totalPages - 2)
    return [1, 2, "ellipsis", totalPages - 2, totalPages - 1, totalPages];
  return [1, currentPage - 1, currentPage, "ellipsis", currentPage + 1, totalPages];
}

function getRecordRange(
  total: number,
  page: number,
  pageSize: number,
  t: ReturnType<typeof useTranslation>["t"],
): string {
  if (total <= 0) return t("dashboard.records.rangeEmpty");
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return t("dashboard.records.range", {
    start: formatNumber(start),
    end: formatNumber(end),
    total: formatNumber(total),
  });
}

export function DashboardRecordsTab({
  data,
  query,
  totalPages,
  isLoading,
  updateQuery,
}: DashboardRecordsTabProps) {
  const { t } = useTranslation();
  const [inputRecord, setInputRecord] = useState<DashboardAuditRecord | null>(null);
  const [outputRecord, setOutputRecord] = useState<DashboardAuditRecord | null>(null);
  const promptQuery = useQuery({
    queryKey: ["dashboard", "llm-api", "record-prompt", inputRecord?.id],
    queryFn: () => fetchDashboardRecordPrompt(inputRecord?.id ?? ""),
    enabled: !!inputRecord,
  });
  const { data: agentDefinitions = [] } = useQuery({
    queryKey: ["agent-definitions"],
    queryFn: fetchAgentDefinitions,
    staleTime: 5 * 60 * 1000,
  });
  const agentNamesByKey = useMemo(
    () => new Map(agentDefinitions.map((definition) => [definition.key, definition.display_name])),
    [agentDefinitions],
  );
  const promptEntries = useMemo(
    () => getPromptEntries(promptQuery.data?.requestMessages),
    [promptQuery.data?.requestMessages],
  );
  const toolCallEntries = outputRecord ? getToolCallEntries(outputRecord.responseToolCalls) : [];
  const errorDetails = outputRecord ? hasErrorDetails(outputRecord) : false;
  const recordTotal = data?.records.total ?? 0;
  const visiblePages = getVisiblePages(query.page, totalPages);

  return (
    <section className="dashboard-tab-panel">
      <Card className="dashboard-record-card">
        <div className="dashboard-record-header">
          <Flex
            direction="column"
            gap="1"
          >
            <Text weight="bold">{t("dashboard.records.title")}</Text>
          </Flex>
        </div>
        <div
          className="dashboard-record-table-wrap"
          data-loading={isLoading}
        >
          <table className="dashboard-record-table">
            <thead>
              <tr>
                <th>
                  <SortableHeader
                    label={t("dashboard.records.columnTime")}
                    sortBy="created_at"
                    query={query}
                    updateQuery={updateQuery}
                  />
                </th>
                <th>{t("dashboard.records.columnProject")}</th>
                <th>{t("dashboard.records.columnModel")}</th>
                <th>{t("dashboard.records.columnOperation")}</th>
                <th>
                  <SortableHeader
                    label={t("dashboard.records.columnLatency")}
                    sortBy="latency_ms"
                    query={query}
                    updateQuery={updateQuery}
                  />
                </th>
                <th>
                  <SortableHeader
                    label={t("dashboard.records.columnFirstToken")}
                    sortBy="first_token_ms"
                    query={query}
                    updateQuery={updateQuery}
                  />
                </th>
                <th>
                  <SortableHeader
                    label={t("dashboard.records.columnInput")}
                    sortBy="tokens_input"
                    query={query}
                    updateQuery={updateQuery}
                  />
                </th>
                <th>
                  <SortableHeader
                    label={t("dashboard.records.columnOutput")}
                    sortBy="tokens_output"
                    query={query}
                    updateQuery={updateQuery}
                  />
                </th>
                <th>{t("dashboard.records.columnStatus")}</th>
                <th className="dashboard-record-action-divider">{t("dashboard.records.input")}</th>
                <th className="dashboard-record-action-heading">{t("dashboard.records.output")}</th>
              </tr>
            </thead>
            <tbody>
              {data?.records.items.map((record) => {
                const hasFailed = isFailedRecord(record);
                const recordHasErrorDetails = hasErrorDetails(record);
                const operationLabel =
                  record.category === "agent"
                    ? (agentNamesByKey.get(record.operation) ?? record.operation)
                    : getOperationLabel(record.operation);
                return (
                  <tr key={record.id}>
                    <td className="dashboard-record-time">{formatDateTime(record.createdAt)}</td>
                    <td>
                      <span className="dashboard-record-project">
                        {record.projectTitle || record.projectId}
                      </span>
                    </td>
                    <td>
                      <span className="dashboard-record-model">
                        {record.modelName || record.modelId}
                      </span>
                    </td>
                    <td>{`${getCategoryLabel(record.category)} / ${operationLabel}`}</td>
                    <td>{formatSeconds(record.latencyMs)}</td>
                    <td>{formatSeconds(record.firstTokenMs)}</td>
                    <td className="dashboard-record-token-cell">
                      {hasFailed
                        ? "-"
                        : `${formatNumber(record.tokensInput)}（${formatNumber(record.tokenCache)}）`}
                    </td>
                    <td className="dashboard-record-token-cell">
                      {hasFailed ? "-" : formatNumber(record.tokensOutput)}
                    </td>
                    <td>
                      <Badge
                        color={getStatusColor(record.status)}
                        variant="soft"
                      >
                        {getStatusLabel(record.status)}
                      </Badge>
                    </td>
                    <td className="dashboard-record-action-cell dashboard-record-action-divider">
                      <IconButton
                        aria-label={t("dashboard.records.viewInput")}
                        className="dashboard-record-icon-button"
                        color="gray"
                        size="1"
                        variant="ghost"
                        onClick={() => setInputRecord(record)}
                      >
                        <ScanSearch size={15} />
                      </IconButton>
                    </td>
                    <td className="dashboard-record-action-cell">
                      <IconButton
                        aria-label={t("dashboard.records.viewOutput")}
                        className="dashboard-record-icon-button"
                        color="gray"
                        disabled={hasFailed && !recordHasErrorDetails}
                        size="1"
                        variant="ghost"
                        onClick={() => setOutputRecord(record)}
                      >
                        <Info size={15} />
                      </IconButton>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {isLoading ? (
            <div className="dashboard-record-loading-overlay">
              <Spinner size={18} />
              <Text
                size="2"
                color="gray"
              >
                {t("dashboard.records.loading")}
              </Text>
            </div>
          ) : null}
          {data?.records.items.length === 0 ? (
            <div className="dashboard-empty-state">{t("dashboard.records.empty")}</div>
          ) : null}
        </div>
        <div className="dashboard-table-footer">
          <Text
            size="2"
            color="gray"
          >
            {getRecordRange(recordTotal, query.page, query.pageSize, t)}
          </Text>
          <div className="dashboard-pagination">
            <Text
              className="dashboard-pagination-total"
              size="2"
              color="gray"
            >
              {t("dashboard.records.totalPages", { total: formatNumber(totalPages) })}
            </Text>
            <IconButton
              className="dashboard-pagination-arrow"
              aria-label={t("dashboard.records.prevPage")}
              color="gray"
              disabled={query.page <= 1 || isLoading}
              size="1"
              variant="ghost"
              onClick={() => updateQuery({ page: query.page - 1 })}
            >
              <ChevronLeft size={14} />
            </IconButton>
            <div
              className="dashboard-pagination-pages"
              aria-label={t("dashboard.records.pageList")}
            >
              {visiblePages.map((page, index) =>
                page === "ellipsis" ? (
                  <span
                    className="dashboard-pagination-ellipsis"
                    key={`ellipsis-${index}`}
                  >
                    ...
                  </span>
                ) : (
                  <button
                    type="button"
                    className="dashboard-pagination-page"
                    data-active={page === query.page}
                    disabled={isLoading || page === query.page}
                    key={page}
                    onClick={() => updateQuery({ page })}
                  >
                    {page}
                  </button>
                ),
              )}
            </div>
            <IconButton
              className="dashboard-pagination-arrow"
              aria-label={t("dashboard.records.nextPage")}
              color="gray"
              disabled={query.page >= totalPages || isLoading}
              size="1"
              variant="ghost"
              onClick={() => updateQuery({ page: query.page + 1 })}
            >
              <ChevronRight size={14} />
            </IconButton>
          </div>
        </div>
      </Card>

      <PromptChainDialog
        open={!!inputRecord}
        onOpenChange={(open) => !open && setInputRecord(null)}
        entries={promptEntries}
        isLoading={promptQuery.isFetching}
        title={t("dashboard.records.inputDialogTitle")}
        description={getRecordDescription(inputRecord, t)}
      />

      <Dialog.Root
        open={!!outputRecord}
        onOpenChange={(open) => !open && setOutputRecord(null)}
      >
        <Dialog.Content className="dashboard-output-dialog-content">
          <Dialog.Title>{t("dashboard.records.outputDialogTitle")}</Dialog.Title>
          <Dialog.Description
            size="2"
            mb="4"
          >
            {t("dashboard.records.outputDialogDescription")}
          </Dialog.Description>
          <ScrollArea className="dashboard-output-scroll-area">
            <Box className="dashboard-output-content">
              {outputRecord?.responseContent ? (
                <section className="dashboard-output-section">
                  <div className="dashboard-output-section-header">
                    <Text
                      as="p"
                      className="dashboard-output-section-title"
                      size="1"
                      weight="medium"
                    >
                      {t("dashboard.records.outputSectionContent")}
                    </Text>
                  </div>
                  <pre className="dashboard-output-text">{outputRecord.responseContent}</pre>
                </section>
              ) : null}

              {toolCallEntries.length > 0 ? (
                <section className="dashboard-output-section">
                  <div className="dashboard-output-section-header">
                    <Text
                      as="p"
                      className="dashboard-output-section-title"
                      size="1"
                      weight="medium"
                    >
                      {t("dashboard.records.outputSectionToolCalls")}
                    </Text>
                  </div>
                  <div className="dashboard-output-tool-call-list">
                    {toolCallEntries.map((toolCall, index) => (
                      <details
                        className="dashboard-output-tool-call"
                        key={`${toolCall.name ?? "tool-call"}-${index}`}
                      >
                        <summary className="dashboard-output-tool-call-summary">
                          {toolCall.name ||
                            t("dashboard.records.toolCallFallback", { index: index + 1 })}
                        </summary>
                        <pre className="dashboard-output-json">{toolCall.content}</pre>
                      </details>
                    ))}
                  </div>
                </section>
              ) : null}

              {outputRecord && errorDetails ? (
                <section className="dashboard-output-section dashboard-output-error-card">
                  <div className="dashboard-output-section-header">
                    <Text
                      as="p"
                      className="dashboard-output-section-title"
                      size="1"
                      weight="medium"
                    >
                      {t("dashboard.records.outputSectionError")}
                    </Text>
                    <div className="dashboard-output-error-meta">
                      <span className="dashboard-output-error-type">
                        {outputRecord.errorType || t("dashboard.records.unknownError")}
                      </span>
                      {typeof outputRecord.errorStatusCode === "number" ? (
                        <Badge
                          color="red"
                          size="1"
                          variant="soft"
                        >
                          {t("dashboard.records.httpStatus", {
                            statusCode: outputRecord.errorStatusCode,
                          })}
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                  {outputRecord.errorMessage ? (
                    <pre className="dashboard-output-json">
                      {stringifyContent(outputRecord.errorMessage)}
                    </pre>
                  ) : null}
                </section>
              ) : null}

              {!outputRecord?.responseContent && toolCallEntries.length === 0 && !errorDetails ? (
                <Text color="gray">{t("dashboard.records.noOutput")}</Text>
              ) : null}
            </Box>
          </ScrollArea>
          <Flex
            justify="end"
            mt="4"
          >
            <Dialog.Close>
              <Button
                color="gray"
                variant="soft"
              >
                {t("common.close")}
              </Button>
            </Dialog.Close>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </section>
  );
}
