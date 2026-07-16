export interface DashboardQueryParams {
  projectId?: string;
  modelProvider?: string;
  modelId?: string;
  category?: string;
  operation?: string;
  status?: string;
  taskId?: string;
  sessionId?: string;
  startAt?: string;
  endAt?: string;
  search?: string;
  page: number;
  pageSize: number;
  sortBy: DashboardSortBy;
  sortOrder: DashboardSortOrder;
}

export type DashboardSortBy =
  | "created_at"
  | "tokens_input"
  | "tokens_output"
  | "tokens_total"
  | "latency_ms"
  | "first_token_ms"
  | "tool_calls_count";

export type DashboardSortOrder = "asc" | "desc";

export interface DashboardSummary {
  callsTotal: number;
  successTotal: number;
  tokensTotal: number;
  tokensInputTotal: number;
  tokensOutputTotal: number;
  avgLatencyMs: number;
  avgFirstTokenMs: number;
}

export interface DashboardTimeSeriesPoint {
  date: string;
  calls: number;
  tokensTotal: number;
  avgLatencyMs: number;
}

export interface DashboardModelTimeSeriesPoint extends DashboardTimeSeriesPoint {
  key: string;
  label: string;
}

export interface DashboardBreakdownItem {
  key: string;
  label: string;
  calls: number;
  tokensTotal: number;
}

export interface DashboardAuditRecord {
  id: string;
  createdAt: string;
  taskId: string | null;
  sessionId: string | null;
  projectId: string;
  projectTitle: string | null;
  chapterId: string | null;
  revisionId: string | null;
  category: string;
  operation: string;
  modelId: string;
  modelProvider: string | null;
  modelName: string | null;
  tokensInput: number;
  tokensOutput: number;
  tokensTotal: number;
  tokenCache: number;
  latencyMs: number | null;
  firstTokenMs: number | null;
  status: string;
  errorType: string | null;
  errorMessage: string | null;
  errorStatusCode: number | null;
  toolCallsCount: number;
  hasRequestMessages: boolean;
  toolReferences: string | null;
  responseContent: string | null;
  responseToolCalls: string | null;
}

export interface DashboardRecordPrompt {
  id: string;
  requestMessages: string | null;
}

export interface DashboardRecordList {
  items: DashboardAuditRecord[];
  total: number;
  page: number;
  pageSize: number;
}

export interface DashboardFilterOptions {
  projectIds: string[];
  modelProviders: string[];
  modelIds: string[];
  categories: string[];
  operations: string[];
  statuses: string[];
  projectOptions: DashboardFilterOptionItem[];
  modelOptions: DashboardFilterOptionItem[];
}

export interface DashboardFilterOptionItem {
  value: string;
  label: string;
}

export interface DashboardStatsResponse {
  summary: DashboardSummary;
  modelTimeSeries: DashboardModelTimeSeriesPoint[];
  byModel: DashboardBreakdownItem[];
  byProject: DashboardBreakdownItem[];
  options: DashboardFilterOptions;
}

export interface DashboardRecordsResponse {
  options: DashboardFilterOptions;
  records: DashboardRecordList;
}

export type WritingActivitySource = "user" | "agent" | "import";

export interface WritingDashboardQueryParams {
  projectId?: string;
  source?: WritingActivitySource;
  startAt?: string;
  endAt?: string;
  timezone?: string;
}

export interface WritingActivitySummary {
  activeDays: number;
  creativeChapters: number;
}

export interface WritingActivityTimeSeriesPoint {
  date: string;
  userWordDelta: number;
  agentWordDelta: number;
  importWordDelta: number;
}

export interface WritingDashboardResponse {
  summary: WritingActivitySummary;
  timeSeries: WritingActivityTimeSeriesPoint[];
}
