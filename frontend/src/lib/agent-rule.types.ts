export interface AgentRule {
  id: string;
  title: string;
  content: string;
  scope: string;
  projectId: string | null;
  tokenCount: number;
  orderIndex: number;
  createdAt: string;
  updatedAt: string;
}

export interface AgentRuleCreate {
  title: string;
  content: string;
  scope?: string;
  projectId?: string | null;
}

export interface AgentRuleUpdate {
  title?: string;
  content?: string;
}

export interface AgentRuleScope {
  scope: string;
  projectId: string | null;
  title: string;
  ruleCount: number;
}

export interface AgentRuleScopeListResponse {
  items: AgentRuleScope[];
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
  scope?: string;
  projectId?: string | null;
}
