export interface AgentMemory {
  id: string;
  content: string;
  orderIndex: number;
  createdAt: string;
  updatedAt: string;
}

export interface AgentMemoryCreate {
  content: string;
}

export interface AgentMemoryUpdate {
  content?: string;
}

export interface AgentMemoryListResponse {
  items: AgentMemory[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AgentMemoryListParams {
  page?: number;
  pageSize?: number;
}
