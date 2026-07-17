/**
 * Model API
 *
 * 模型和提供商 API 客户端。
 */

import { apiClient } from "@/lib/api-client";
import type {
  AvailableModel,
  Model,
  ModelCreateRequest,
  ModelProviderCatalogMatch,
  ModelProviderCatalogModelsResponse,
  ModelProviderCatalogProvider,
  ModelProvider,
  ModelProviderResponse,
  ModelProviderValidateRequest,
  ModelProviderValidateResponse,
  ModelProviderCatalogModel,
  ModelResponse,
  TaskType,
  ModelUpdateRequest,
} from "@/lib/model.types";

interface ModelProviderCatalogProviderResponse {
  provider_type: string;
  display_name: string;
  default_url: string | null;
  api: string | null;
  icon_path: string | null;
  models_dev_provider_id: string | null;
  supported_task_types: string[];
  model_counts: Partial<Record<TaskType, number>>;
}

interface ModelProviderCatalogModelResponse {
  model_id: string;
  display_name: string;
  task_type: TaskType;
  metadata: {
    release_date?: string | null;
    reasoning?: boolean | null;
    tool_call?: boolean | null;
    modalities?: {
      input?: string[];
      output?: string[];
    } | null;
    limit?: Record<string, unknown> | string | number | null;
    cost?: Record<string, unknown> | string | number | null;
  } | null;
}

interface ModelProviderAvailableModelApiResponse {
  id: string;
  name: string;
  task_type?: TaskType | null;
  metadata?: ModelProviderCatalogModelResponse["metadata"];
}

interface ModelProviderValidateApiResponse {
  success: boolean;
  message: string;
  models: ModelProviderAvailableModelApiResponse[];
}

interface ModelProviderCatalogModelsApiResponse {
  provider: ModelProviderCatalogProviderResponse;
  task_type: TaskType;
  models: ModelProviderCatalogModelResponse[];
}

function readNumericMetadataField(
  value: Record<string, unknown> | string | number | null | undefined,
  key: string,
): number | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  const entry = value[key];
  if (typeof entry === "number") {
    return Number.isFinite(entry) ? entry : null;
  }
  if (typeof entry === "string") {
    const parsed = Number(entry);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

function transformCatalogMatch(
  raw: NonNullable<ModelProviderResponse["catalog_match"]> | null | undefined,
): ModelProviderCatalogMatch | null {
  if (!raw) {
    return null;
  }

  return {
    catalogProviderType: raw.catalog_provider_type,
    displayName: raw.display_name,
    defaultUrl: raw.default_url,
    api: raw.api,
    iconPath: raw.icon_path,
    modelsDevProviderId: raw.models_dev_provider_id,
    matchedVia: raw.matched_via,
  };
}

/**
 * 后端响应字段转换（snake_case -> camelCase）- Provider
 */
function transformProvider(raw: ModelProviderResponse): ModelProvider {
  return {
    id: raw.id,
    name: raw.name,
    url: raw.url,
    providerType: raw.provider_type as ModelProvider["providerType"],
    supportedTaskTypes: raw.supported_task_types as ModelProvider["supportedTaskTypes"],
    iconPath: raw.icon_path || null,
    isBuiltin: raw.is_builtin ?? false,
    catalogMatch: transformCatalogMatch(raw.catalog_match),
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

/**
 * 后端响应字段转换（snake_case -> camelCase）- Model
 */
function transformModel(raw: ModelResponse): Model {
  return {
    id: raw.id,
    name: raw.name,
    remark: raw.remark,
    providerId: raw.provider_id,
    modelId: raw.model_id,
    taskType: raw.task_type,
    temperature: raw.temperature,
    topP: raw.top_p,
    topK: raw.top_k,
    minP: raw.min_p,
    topA: raw.top_a,
    frequencyPenalty: raw.frequency_penalty,
    presencePenalty: raw.presence_penalty,
    repetitionPenalty: raw.repetition_penalty,
    maxTokens: raw.max_tokens,
    contextLength: raw.context_length ?? 128000,
    dimensions: raw.dimensions,
    isBuiltin: raw.is_builtin ?? false,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

function transformCatalogProvider(
  raw: ModelProviderCatalogProviderResponse,
): ModelProviderCatalogProvider {
  return {
    providerType: raw.provider_type,
    displayName: raw.display_name,
    defaultUrl: raw.default_url,
    api: raw.api,
    iconPath: raw.icon_path,
    modelsDevProviderId: raw.models_dev_provider_id,
    supportedTaskTypes:
      raw.supported_task_types as ModelProviderCatalogProvider["supportedTaskTypes"],
    modelCounts: raw.model_counts ?? {},
  };
}

function transformCatalogModel(raw: ModelProviderCatalogModelResponse): ModelProviderCatalogModel {
  const metadata = raw.metadata ?? null;

  return {
    id: raw.model_id,
    name: raw.display_name,
    taskType: raw.task_type,
    releaseDate: metadata?.release_date ?? null,
    reasoning: metadata?.reasoning ?? null,
    toolCall: metadata?.tool_call ?? null,
    inputModalities: metadata?.modalities?.input ?? [],
    limit: metadata?.limit ?? null,
    cost: metadata?.cost ?? null,
    contextWindow: readNumericMetadataField(metadata?.limit, "context"),
    inputPricePerMillion: readNumericMetadataField(metadata?.cost, "input"),
    outputPricePerMillion: readNumericMetadataField(metadata?.cost, "output"),
    cacheReadPricePerMillion: readNumericMetadataField(metadata?.cost, "cache_read"),
    source: "catalog",
  };
}

function transformAvailableModel(
  raw: ModelProviderAvailableModelApiResponse,
  source: "catalog" | "remote",
): AvailableModel {
  const metadata = raw.metadata ?? null;

  return {
    id: raw.id,
    name: raw.name,
    taskType: raw.task_type ?? null,
    releaseDate: metadata?.release_date ?? null,
    reasoning: metadata?.reasoning ?? null,
    toolCall: metadata?.tool_call ?? null,
    inputModalities: metadata?.modalities?.input ?? [],
    limit: metadata?.limit ?? null,
    cost: metadata?.cost ?? null,
    contextWindow: readNumericMetadataField(metadata?.limit, "context"),
    inputPricePerMillion: readNumericMetadataField(metadata?.cost, "input"),
    outputPricePerMillion: readNumericMetadataField(metadata?.cost, "output"),
    cacheReadPricePerMillion: readNumericMetadataField(metadata?.cost, "cache_read"),
    source,
  };
}

// ========== Provider APIs ==========

/**
 * 获取所有提供商
 */
export async function fetchProviders(): Promise<ModelProvider[]> {
  const response = await apiClient.get<ModelProviderResponse[]>("/model-providers");
  return response.data.map(transformProvider);
}

/**
 * 根据 ID 获取提供商
 */
export async function fetchProvider(id: string): Promise<ModelProvider> {
  const response = await apiClient.get<ModelProviderResponse>(`/model-providers/${id}`);
  return transformProvider(response.data);
}

/**
 * 创建提供商
 */
export async function createProvider(data: FormData): Promise<ModelProvider> {
  const response = await apiClient.post<ModelProviderResponse>("/model-providers", data, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return transformProvider(response.data);
}

/**
 * 更新提供商
 */
export async function updateProvider(id: string, data: FormData): Promise<ModelProvider> {
  const response = await apiClient.put<ModelProviderResponse>(`/model-providers/${id}`, data, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return transformProvider(response.data);
}

/**
 * 删除提供商
 */
export async function deleteProvider(id: string): Promise<void> {
  await apiClient.delete(`/model-providers/${id}`);
}

/**
 * 验证提供商连接
 */
export async function validateProvider(
  data: ModelProviderValidateRequest,
): Promise<ModelProviderValidateResponse> {
  const response = await apiClient.post<ModelProviderValidateApiResponse>(
    "/model-providers/validate",
    data,
  );
  return {
    ...response.data,
    models: (response.data.models || []).map((model) => transformAvailableModel(model, "remote")),
  };
}

/**
 * 获取提供商的模型列表
 */
export async function fetchProviderModels(
  providerId: string,
  taskType: TaskType = "llm",
): Promise<ModelProviderValidateResponse> {
  const response = await apiClient.get<ModelProviderValidateApiResponse>(
    `/model-providers/${providerId}/models`,
    { params: { task_type: taskType } },
  );
  return {
    ...response.data,
    models: (response.data.models || []).map((model) => transformAvailableModel(model, "remote")),
  };
}

export async function fetchModelProviderCatalogProviders(): Promise<
  ModelProviderCatalogProvider[]
> {
  const response = await apiClient.get<ModelProviderCatalogProviderResponse[]>(
    "/model-provider-catalog/providers",
  );
  return response.data.map(transformCatalogProvider);
}

export async function fetchModelProviderCatalogModels(
  providerType: string,
  taskType: TaskType,
): Promise<ModelProviderCatalogModelsResponse> {
  const response = await apiClient.get<ModelProviderCatalogModelsApiResponse>(
    `/model-provider-catalog/providers/${providerType}/models`,
    { params: { task_type: taskType } },
  );

  return {
    provider: transformCatalogProvider(response.data.provider),
    models: (response.data.models || []).map(transformCatalogModel),
  };
}

// ========== Model APIs ==========

/**
 * 获取所有模型
 */
export async function fetchModels(providerId?: string, taskType?: string): Promise<Model[]> {
  const params: Record<string, string> = {};
  if (providerId) params.provider_id = providerId;
  if (taskType) params.task_type = taskType;
  const response = await apiClient.get<ModelResponse[]>("/models", { params });
  return response.data.map(transformModel);
}

/**
 * 根据 ID 获取模型
 */
export async function fetchModel(id: string): Promise<Model> {
  const response = await apiClient.get<ModelResponse>(`/models/${id}`);
  return transformModel(response.data);
}

/**
 * 创建模型
 */
export async function createModel(data: ModelCreateRequest): Promise<Model> {
  const response = await apiClient.post<ModelResponse>("/models", data);
  return transformModel(response.data);
}

/**
 * 更新模型
 */
export async function updateModel(id: string, data: ModelUpdateRequest): Promise<Model> {
  const response = await apiClient.put<ModelResponse>(`/models/${id}`, data);
  return transformModel(response.data);
}

/**
 * 删除模型
 */
export async function deleteModel(id: string): Promise<void> {
  await apiClient.delete(`/models/${id}`);
}
