/**
 * Agent Definitions API
 *
 * Klien API definisi agen, terhubung ke /agent-definitions di backend.
 */

import { apiClient } from "@/lib/api-client";

import type {
  AgentDefinitionCreateRequest,
  AgentDefinitionListResponse,
  AgentDefinitionResponse,
  AgentToolCategoryListResponse,
  AgentToolCategoryResponse,
  AgentDefinitionUpdateRequest,
} from "./agent-definitions.types";

export async function fetchAgentDefinitions(): Promise<AgentDefinitionResponse[]> {
  const response = await apiClient.get<AgentDefinitionListResponse>("/agent-definitions");
  return response.data.definitions;
}

export async function fetchAgentDefinition(key: string): Promise<AgentDefinitionResponse> {
  const response = await apiClient.get<AgentDefinitionResponse>(`/agent-definitions/${key}`);
  return response.data;
}

export async function fetchAgentToolCategories(): Promise<AgentToolCategoryResponse[]> {
  const response = await apiClient.get<AgentToolCategoryListResponse>(
    "/agent-definitions/tool-categories",
  );
  return response.data.categories;
}

export async function createAgentDefinition(
  data: AgentDefinitionCreateRequest,
): Promise<AgentDefinitionResponse> {
  const response = await apiClient.post<AgentDefinitionResponse>("/agent-definitions", data);
  return response.data;
}

export async function updateAgentDefinition(
  key: string,
  data: AgentDefinitionUpdateRequest,
): Promise<AgentDefinitionResponse> {
  const response = await apiClient.put<AgentDefinitionResponse>(`/agent-definitions/${key}`, data);
  return response.data;
}

export async function resetAgentDefinition(key: string): Promise<AgentDefinitionResponse> {
  const response = await apiClient.post<AgentDefinitionResponse>(`/agent-definitions/${key}/reset`);
  return response.data;
}

export async function deleteAgentDefinition(key: string): Promise<void> {
  await apiClient.delete(`/agent-definitions/${key}`);
}
