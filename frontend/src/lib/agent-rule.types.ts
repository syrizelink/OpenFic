export interface AgentRule {
  id: string;
  title: string;
  content: string;
  orderIndex: number;
  createdAt: string;
  updatedAt: string;
}

export interface AgentRuleCreate {
  title: string;
  content: string;
}

export interface AgentRuleUpdate {
  title?: string;
  content?: string;
}

export interface AgentRuleListResponse {
  items: AgentRule[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AgentRuleListParams {
  page?: number;
  pageSize?: number;
}
