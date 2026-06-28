import { apiClient } from "@/lib/api-client";
import type {
  DashboardAuditRecord,
  DashboardBreakdownItem,
  DashboardFilterOptions,
  DashboardModelTimeSeriesPoint,
  DashboardQueryParams,
  DashboardRecordList,
  DashboardRecordPrompt,
  DashboardRecordsResponse,
  DashboardStatsResponse,
  DashboardSummary,
  DashboardTimeSeriesPoint,
  WritingActivitySummary,
  WritingActivityTimeSeriesPoint,
  WritingDashboardQueryParams,
  WritingDashboardResponse,
} from "./dashboard.types";

interface RawDashboardSummary {
  calls_total: number;
  success_total: number;
  tokens_total: number;
  tokens_input_total: number;
  tokens_output_total: number;
  avg_latency_ms: number;
  avg_first_token_ms: number;
}

interface RawDashboardTimeSeriesPoint {
  date: string;
  calls: number;
  tokens_total: number;
  avg_latency_ms: number;
}

interface RawDashboardModelTimeSeriesPoint extends RawDashboardTimeSeriesPoint {
  key: string;
  label: string;
}

interface RawDashboardBreakdownItem {
  key: string;
  label: string;
  calls: number;
  tokens_total: number;
}

interface RawDashboardAuditRecord {
  id: string;
  created_at: string;
  task_id: string | null;
  session_id: string | null;
  project_id: string;
  project_title: string | null;
  chapter_id: string | null;
  revision_id: string | null;
  agent_node: string;
  model_id: string;
  model_provider: string | null;
  model_name: string | null;
  tokens_input: number;
  tokens_output: number;
  tokens_total: number;
  token_cache: number;
  latency_ms: number | null;
  first_token_ms: number | null;
  status: string;
  error_type: string | null;
  error_message: string | null;
  error_status_code: number | null;
  tool_calls_count: number;
  response_content: string | null;
  response_tool_calls: string | null;
}

interface RawDashboardRecordPrompt {
  id: string;
  request_messages: string | null;
}

interface RawDashboardRecordList {
  items: RawDashboardAuditRecord[];
  total: number;
  page: number;
  page_size: number;
}

interface RawDashboardFilterOptions {
  project_ids: string[];
  model_providers: string[];
  model_ids: string[];
  agent_nodes: string[];
  statuses: string[];
  project_options: RawDashboardFilterOptionItem[];
  model_options: RawDashboardFilterOptionItem[];
}

interface RawDashboardFilterOptionItem {
  value: string;
  label: string;
}

interface RawDashboardStatsResponse {
  summary: RawDashboardSummary;
  model_time_series: RawDashboardModelTimeSeriesPoint[];
  by_model: RawDashboardBreakdownItem[];
  by_project: RawDashboardBreakdownItem[];
  options: RawDashboardFilterOptions;
}

interface RawDashboardRecordsResponse {
  options: RawDashboardFilterOptions;
  records: RawDashboardRecordList;
}

interface RawWritingActivitySummary {
  active_days: number;
  creative_chapters: number;
}

interface RawWritingActivityTimeSeriesPoint {
  date: string;
  user_word_delta: number;
  agent_word_delta: number;
  import_word_delta: number;
}

interface RawWritingDashboardResponse {
  summary: RawWritingActivitySummary;
  time_series: RawWritingActivityTimeSeriesPoint[];
}

function transformSummary(raw: RawDashboardSummary): DashboardSummary {
  return {
    callsTotal: raw.calls_total,
    successTotal: raw.success_total,
    tokensTotal: raw.tokens_total,
    tokensInputTotal: raw.tokens_input_total,
    tokensOutputTotal: raw.tokens_output_total,
    avgLatencyMs: raw.avg_latency_ms,
    avgFirstTokenMs: raw.avg_first_token_ms,
  };
}

function transformTimeSeriesPoint(
  raw: RawDashboardTimeSeriesPoint
): DashboardTimeSeriesPoint {
  return {
    date: raw.date,
    calls: raw.calls,
    tokensTotal: raw.tokens_total,
    avgLatencyMs: raw.avg_latency_ms,
  };
}

function transformModelTimeSeriesPoint(
  raw: RawDashboardModelTimeSeriesPoint
): DashboardModelTimeSeriesPoint {
  return {
    ...transformTimeSeriesPoint(raw),
    key: raw.key,
    label: raw.label,
  };
}

function transformBreakdownItem(raw: RawDashboardBreakdownItem): DashboardBreakdownItem {
  return {
    key: raw.key,
    label: raw.label,
    calls: raw.calls,
    tokensTotal: raw.tokens_total,
  };
}

function transformRecord(raw: RawDashboardAuditRecord): DashboardAuditRecord {
  return {
    id: raw.id,
    createdAt: raw.created_at,
    taskId: raw.task_id,
    sessionId: raw.session_id,
    projectId: raw.project_id,
    projectTitle: raw.project_title,
    chapterId: raw.chapter_id,
    revisionId: raw.revision_id,
    agentNode: raw.agent_node,
    modelId: raw.model_id,
    modelProvider: raw.model_provider,
    modelName: raw.model_name,
    tokensInput: raw.tokens_input,
    tokensOutput: raw.tokens_output,
    tokensTotal: raw.tokens_total,
    tokenCache: raw.token_cache,
    latencyMs: raw.latency_ms,
    firstTokenMs: raw.first_token_ms,
    status: raw.status,
    errorType: raw.error_type,
    errorMessage: raw.error_message,
    errorStatusCode: raw.error_status_code,
    toolCallsCount: raw.tool_calls_count,
    responseContent: raw.response_content,
    responseToolCalls: raw.response_tool_calls,
  };
}

function transformRecordPrompt(raw: RawDashboardRecordPrompt): DashboardRecordPrompt {
  return {
    id: raw.id,
    requestMessages: raw.request_messages,
  };
}

function transformRecords(raw: RawDashboardRecordList): DashboardRecordList {
  return {
    items: raw.items.map(transformRecord),
    total: raw.total,
    page: raw.page,
    pageSize: raw.page_size,
  };
}

function transformOptions(raw: RawDashboardFilterOptions): DashboardFilterOptions {
  return {
    projectIds: raw.project_ids,
    modelProviders: raw.model_providers,
    modelIds: raw.model_ids,
    agentNodes: raw.agent_nodes,
    statuses: raw.statuses,
    projectOptions: raw.project_options.map((option) => ({ value: option.value, label: option.label })),
    modelOptions: raw.model_options.map((option) => ({ value: option.value, label: option.label })),
  };
}

function transformWritingSummary(raw: RawWritingActivitySummary): WritingActivitySummary {
  return {
    activeDays: raw.active_days,
    creativeChapters: raw.creative_chapters,
  };
}

function transformWritingTimeSeriesPoint(
  raw: RawWritingActivityTimeSeriesPoint
): WritingActivityTimeSeriesPoint {
  return {
    date: raw.date,
    userWordDelta: raw.user_word_delta,
    agentWordDelta: raw.agent_word_delta,
    importWordDelta: raw.import_word_delta,
  };
}

export async function fetchLlmDashboardStats(
  query: DashboardQueryParams
): Promise<DashboardStatsResponse> {
  const response = await apiClient.get<RawDashboardStatsResponse>("/dashboard/llm-api/stats", {
    params: {
      project_id: query.projectId || undefined,
      model_provider: query.modelProvider || undefined,
      model_id: query.modelId || undefined,
      agent_node: query.agentNode || undefined,
      status: query.status || undefined,
      start_at: query.startAt || undefined,
      end_at: query.endAt || undefined,
    },
  });
  const raw = response.data;
  return {
    summary: transformSummary(raw.summary),
    modelTimeSeries: raw.model_time_series.map(transformModelTimeSeriesPoint),
    byModel: raw.by_model.map(transformBreakdownItem),
    byProject: raw.by_project.map(transformBreakdownItem),
    options: transformOptions(raw.options),
  };
}

export async function fetchLlmDashboardRecords(
  query: DashboardQueryParams
): Promise<DashboardRecordsResponse> {
  const response = await apiClient.get<RawDashboardRecordsResponse>("/dashboard/llm-api/records", {
    params: {
      project_id: query.projectId || undefined,
      model_provider: query.modelProvider || undefined,
      model_id: query.modelId || undefined,
      agent_node: query.agentNode || undefined,
      status: query.status || undefined,
      task_id: query.taskId || undefined,
      session_id: query.sessionId || undefined,
      start_at: query.startAt || undefined,
      end_at: query.endAt || undefined,
      search: query.search || undefined,
      page: query.page,
      page_size: query.pageSize,
      sort_by: query.sortBy,
      sort_order: query.sortOrder,
    },
  });
  const raw = response.data;
  return {
    options: transformOptions(raw.options),
    records: transformRecords(raw.records),
  };
}

export async function fetchDashboardRecordPrompt(recordId: string): Promise<DashboardRecordPrompt> {
  const response = await apiClient.get<RawDashboardRecordPrompt>(`/dashboard/llm-api/records/${recordId}/prompt`);
  return transformRecordPrompt(response.data);
}

export async function fetchWritingDashboard(
  query: WritingDashboardQueryParams
): Promise<WritingDashboardResponse> {
  const response = await apiClient.get<RawWritingDashboardResponse>("/dashboard/writing", {
    params: {
      project_id: query.projectId || undefined,
      source: query.source || undefined,
      start_at: query.startAt || undefined,
      end_at: query.endAt || undefined,
      timezone: query.timezone || undefined,
    },
  });
  const raw = response.data;
  return {
    summary: transformWritingSummary(raw.summary),
    timeSeries: raw.time_series.map(transformWritingTimeSeriesPoint),
  };
}
