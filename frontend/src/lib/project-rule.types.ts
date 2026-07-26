export interface ProjectRule {
  id: string;
  projectId: string;
  title: string;
  content: string;
  orderIndex: number;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectRuleCreate {
  title: string;
  content: string;
}

export interface ProjectRuleUpdate {
  title?: string;
  content?: string;
}

export interface ProjectRuleListResponse {
  items: ProjectRule[];
  total: number;
  page: number;
  pageSize: number;
}

export interface ProjectRuleListParams {
  page?: number;
  pageSize?: number;
}
