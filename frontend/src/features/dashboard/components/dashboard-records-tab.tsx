import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge, Box, Button, Card, Dialog, Flex, IconButton, ScrollArea, Text } from "@radix-ui/themes";
import { ArrowDownNarrowWide, ArrowUpDown, ArrowUpWideNarrow, ChevronLeft, ChevronRight, Info, ScanSearch } from "lucide-react";
import { PromptChainDialog } from "@/components";
import type { PromptChainDialogEntry } from "@/components";
import { fetchDashboardRecordPrompt } from "../lib/dashboard-api";
import { formatDateTime, formatNumber, formatSeconds, getAgentLabel, getStatusLabel } from "../lib/dashboard-formatters";
import type { DashboardAuditRecord, DashboardQueryParams, DashboardRecordsResponse, DashboardSortBy } from "../lib/dashboard.types";

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
    if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
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
    const toolCalls = Array.isArray(item.tool_calls) && item.tool_calls.length > 0
      ? `\n\nTool calls:\n${JSON.stringify(item.tool_calls, null, 2)}`
      : "";

    return {
      role,
      content: `${content}${toolCalls}`,
      name: `#${index + 1}`,
    };
  });
}

function formatOutputContent(record: DashboardAuditRecord): string {
  const sections: string[] = [];
  if (record.responseContent) {
    sections.push(`Content\n${record.responseContent}`);
  }

  const toolCalls = parseJson(record.responseToolCalls);
  if (toolCalls) {
    sections.push(`Tool calls\n${typeof toolCalls === "string" ? toolCalls : JSON.stringify(toolCalls, null, 2)}`);
  }

  if (record.errorMessage || record.errorType) {
    sections.push(`Error\n${record.errorMessage || record.errorType}`);
  }

  return sections.join("\n\n");
}

function getStatusColor(status: string): "green" | "red" | "gray" {
  if (status === "success") return "green";
  if (status === "error" || status === "failed" || status === "failure") return "red";
  return "gray";
}

function isFailedRecord(record: DashboardAuditRecord): boolean {
  return record.status === "error" || record.status === "failed" || record.status === "failure";
}

function getRecordDescription(record: DashboardAuditRecord | null): string | undefined {
  if (!record) return undefined;
  const modelName = record.modelName || record.modelId;
  const projectName = record.projectTitle || "未知项目";
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
  const SortIcon = !isActive ? ArrowUpDown : query.sortOrder === "desc" ? ArrowDownNarrowWide : ArrowUpWideNarrow;

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
      <SortIcon size={14} aria-hidden="true" />
    </button>
  );
}

function getVisiblePages(currentPage: number, totalPages: number): Array<number | "ellipsis"> {
  if (totalPages <= 6) return Array.from({ length: totalPages }, (_, index) => index + 1);
  if (currentPage <= 3) return [1, 2, 3, "ellipsis", totalPages - 1, totalPages];
  if (currentPage >= totalPages - 2) return [1, 2, "ellipsis", totalPages - 2, totalPages - 1, totalPages];
  return [1, currentPage - 1, currentPage, "ellipsis", currentPage + 1, totalPages];
}

function getRecordRange(total: number, page: number, pageSize: number): string {
  if (total <= 0) return "第 0 - 0 条，共 0 条";
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return `第 ${formatNumber(start)} - ${formatNumber(end)} 条，共 ${formatNumber(total)} 条`;
}

export function DashboardRecordsTab({ data, query, totalPages, isLoading, updateQuery }: DashboardRecordsTabProps) {
  const [inputRecord, setInputRecord] = useState<DashboardAuditRecord | null>(null);
  const [outputRecord, setOutputRecord] = useState<DashboardAuditRecord | null>(null);
  const promptQuery = useQuery({
    queryKey: ["dashboard", "llm-api", "record-prompt", inputRecord?.id],
    queryFn: () => fetchDashboardRecordPrompt(inputRecord?.id ?? ""),
    enabled: !!inputRecord,
  });
  const promptEntries = useMemo(
    () => getPromptEntries(promptQuery.data?.requestMessages),
    [promptQuery.data?.requestMessages]
  );
  const outputContent = outputRecord ? formatOutputContent(outputRecord) : "";
  const recordTotal = data?.records.total ?? 0;
  const visiblePages = getVisiblePages(query.page, totalPages);

  return (
    <section className="dashboard-tab-panel">
      <Card className="dashboard-record-card">
        <div className="dashboard-record-header">
          <Flex direction="column" gap="1">
            <Text weight="bold">调用记录</Text>
          </Flex>
        </div>
        <div className="dashboard-record-table-wrap" data-loading={isLoading}>
          <table className="dashboard-record-table">
            <thead>
              <tr>
                <th><SortableHeader label="时间" sortBy="created_at" query={query} updateQuery={updateQuery} /></th>
                <th>项目</th>
                <th>模型</th>
                <th>Agent</th>
                <th><SortableHeader label="用时" sortBy="latency_ms" query={query} updateQuery={updateQuery} /></th>
                <th><SortableHeader label="首字" sortBy="first_token_ms" query={query} updateQuery={updateQuery} /></th>
                <th><SortableHeader label="输入（缓存）" sortBy="tokens_input" query={query} updateQuery={updateQuery} /></th>
                <th><SortableHeader label="输出" sortBy="tokens_output" query={query} updateQuery={updateQuery} /></th>
                <th>状态</th>
                <th className="dashboard-record-action-divider">输入</th>
                <th className="dashboard-record-action-heading">输出</th>
              </tr>
            </thead>
            <tbody>
              {data?.records.items.map((record) => {
                const hasFailed = isFailedRecord(record);
                return (
                  <tr key={record.id}>
                    <td className="dashboard-record-time">{formatDateTime(record.createdAt)}</td>
                    <td>
                      <span className="dashboard-record-project">{record.projectTitle || record.projectId}</span>
                    </td>
                    <td>
                      <span className="dashboard-record-model">{record.modelName || record.modelId}</span>
                    </td>
                    <td>{getAgentLabel(record.agentNode)}</td>
                    <td>{formatSeconds(record.latencyMs)}</td>
                    <td>{formatSeconds(record.firstTokenMs)}</td>
                    <td className="dashboard-record-token-cell">
                      {hasFailed ? "-" : `${formatNumber(record.tokensInput)}（${formatNumber(record.tokenCache)}）`}
                    </td>
                    <td className="dashboard-record-token-cell">{hasFailed ? "-" : formatNumber(record.tokensOutput)}</td>
                    <td>
                      <Badge color={getStatusColor(record.status)} variant="soft">
                        {getStatusLabel(record.status)}
                      </Badge>
                    </td>
                    <td className="dashboard-record-action-cell dashboard-record-action-divider">
                      <IconButton
                        aria-label="查看输入提示词"
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
                        aria-label="查看输出内容"
                        className="dashboard-record-icon-button"
                        color="gray"
                        disabled={hasFailed}
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
              <div className="dashboard-record-loading-spinner" aria-hidden="true" />
              <Text size="2" color="gray">正在载入记录</Text>
            </div>
          ) : null}
          {data?.records.items.length === 0 ? <div className="dashboard-empty-state">没有符合条件的调用记录</div> : null}
        </div>
        <div className="dashboard-table-footer">
          <Text size="2" color="gray">{getRecordRange(recordTotal, query.page, query.pageSize)}</Text>
          <div className="dashboard-pagination">
            <Text className="dashboard-pagination-total" size="2" color="gray">总页数: {formatNumber(totalPages)}</Text>
            <IconButton className="dashboard-pagination-arrow" aria-label="上一页" color="gray" disabled={query.page <= 1 || isLoading} size="1" variant="ghost" onClick={() => updateQuery({ page: query.page - 1 })}>
              <ChevronLeft size={14} />
            </IconButton>
            <div className="dashboard-pagination-pages" aria-label="页码列表">
              {visiblePages.map((page, index) => page === "ellipsis" ? (
                <span className="dashboard-pagination-ellipsis" key={`ellipsis-${index}`}>...</span>
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
              ))}
            </div>
            <IconButton className="dashboard-pagination-arrow" aria-label="下一页" color="gray" disabled={query.page >= totalPages || isLoading} size="1" variant="ghost" onClick={() => updateQuery({ page: query.page + 1 })}>
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
        title="输入提示词"
        description={getRecordDescription(inputRecord)}
      />

      <Dialog.Root open={!!outputRecord} onOpenChange={(open) => !open && setOutputRecord(null)}>
        <Dialog.Content className="dashboard-output-dialog-content">
          <Dialog.Title>输出内容</Dialog.Title>
          <Dialog.Description size="2" mb="4">
            模型输出 content 与 tool calls。
          </Dialog.Description>
          <ScrollArea className="dashboard-output-scroll-area">
            <Box className="dashboard-output-content">
              {outputContent || <Text color="gray">没有输出内容</Text>}
            </Box>
          </ScrollArea>
          <Flex justify="end" mt="4">
            <Dialog.Close>
              <Button color="gray" variant="soft">关闭</Button>
            </Dialog.Close>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </section>
  );
}
