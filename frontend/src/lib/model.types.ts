/**
 * Model and Provider Types
 *
 * 模型和提供商相关类型定义。
 */

/** 提供商类型 */
export type ProviderType =
  | "openai"
  | "anthropic"
  | "google-genai"
  | "ollama"
  | "groq"
  | "huggingface"
  | "mistral"
  | "nvidia-ai-endpoints"
  | "cohere"
  | "openrouter"
  | "amazon-nova"
  | "deepseek"
  | "openai-compatible"
  | "builtin";

/** 任务类型 */
export type TaskType = "llm" | "embedding" | "rerank";

/** 模型服务提供商 */
export interface ModelProvider {
  id: string;
  name: string;
  url: string;
  providerType: ProviderType;
  supportedTaskTypes: TaskType[];
  iconPath: string | null;
  isBuiltin: boolean;
  catalogMatch: ModelProviderCatalogMatch | null;
  createdAt: string;
  updatedAt: string;
}

export type CatalogMatchSource = "provider_type" | "api";

export interface ModelProviderCatalogMatch {
  catalogProviderType: string;
  displayName: string;
  defaultUrl: string | null;
  api: string | null;
  iconPath: string | null;
  modelsDevProviderId: string | null;
  matchedVia: CatalogMatchSource;
}

/** 模型服务提供商响应（后端格式） */
export interface ModelProviderResponse {
  id: string;
  name: string;
  url: string;
  provider_type: string;
  supported_task_types: string[];
  icon_path: string | null;
  is_builtin?: boolean;
  catalog_match?: {
    catalog_provider_type: string;
    display_name: string;
    default_url: string | null;
    api: string | null;
    icon_path: string | null;
    models_dev_provider_id: string | null;
    matched_via: CatalogMatchSource;
  } | null;
  created_at: string;
  updated_at: string;
}

/** 创建/更新提供商请求 (FormData) */
export type ModelProviderFormData = FormData;

/** 验证提供商请求 */
export interface ModelProviderValidateRequest {
  provider_type: string;
  url: string;
  api_key: string;
}

/** 可用模型 */
export interface AvailableModel {
  id: string;
  name: string;
  taskType?: TaskType | null;
  releaseDate?: string | null;
  reasoning?: boolean | null;
  toolCall?: boolean | null;
  inputModalities?: string[];
  limit?: Record<string, unknown> | string | number | null;
  cost?: Record<string, unknown> | string | number | null;
  contextWindow?: number | null;
  inputPricePerMillion?: number | null;
  outputPricePerMillion?: number | null;
  cacheReadPricePerMillion?: number | null;
  source?: "catalog" | "remote";
}

/** 验证提供商响应 */
export interface ModelProviderValidateResponse {
  success: boolean;
  message: string;
  models: AvailableModel[];
}

/** 模型 */
export interface Model {
  id: string;
  name: string;
  remark: string;
  providerId: string;
  modelId: string;
  taskType: TaskType;
  tags: string[];
  temperature: number | null;
  topP: number | null;
  topK: number | null;
  minP: number | null;
  topA: number | null;
  frequencyPenalty: number | null;
  presencePenalty: number | null;
  repetitionPenalty: number | null;
  maxTokens: number | null;
  contextLength: number;
  deepseekReasoningEffort: "high" | "max" | null;
  deepseekThinkingType: "enabled" | "disabled" | null;
  dimensions: number | null;
  isBuiltin: boolean;
  createdAt: string;
  updatedAt: string;
}

/** 模型响应（后端格式） */
export interface ModelResponse {
  id: string;
  name: string;
  remark: string;
  provider_id: string;
  model_id: string;
  task_type: TaskType;
  tags: string[];
  temperature: number | null;
  top_p: number | null;
  top_k: number | null;
  min_p: number | null;
  top_a: number | null;
  frequency_penalty: number | null;
  presence_penalty: number | null;
  repetition_penalty: number | null;
  max_tokens: number | null;
  context_length: number;
  deepseek_reasoning_effort: "high" | "max" | null;
  deepseek_thinking_type: "enabled" | "disabled" | null;
  dimensions: number | null;
  is_builtin?: boolean;
  created_at: string;
  updated_at: string;
}

/** 创建模型请求 */
export interface ModelCreateRequest {
  name: string;
  provider_id: string;
  model_id: string;
  task_type?: TaskType;
  remark?: string;
  tags?: string[];
  temperature?: number | null;
  top_p?: number | null;
  top_k?: number | null;
  min_p?: number | null;
  top_a?: number | null;
  frequency_penalty?: number | null;
  presence_penalty?: number | null;
  repetition_penalty?: number | null;
  max_tokens?: number | null;
  context_length?: number | null;
  deepseek_reasoning_effort?: "high" | "max" | null;
  deepseek_thinking_type?: "enabled" | "disabled" | null;
  dimensions?: number | null;
}

/** 更新模型请求 */
export interface ModelUpdateRequest {
  name?: string;
  remark?: string;
  provider_id?: string;
  model_id?: string;
  task_type?: TaskType;
  tags?: string[];
  temperature?: number | null;
  top_p?: number | null;
  top_k?: number | null;
  min_p?: number | null;
  top_a?: number | null;
  frequency_penalty?: number | null;
  presence_penalty?: number | null;
  repetition_penalty?: number | null;
  max_tokens?: number | null;
  context_length?: number | null;
  deepseek_reasoning_effort?: "high" | "max" | null;
  deepseek_thinking_type?: "enabled" | "disabled" | null;
  dimensions?: number | null;
}

/** 标签响应 */
export interface TagsResponse {
  tags: string[];
}

/** 提供商选项 */
export interface ProviderOption {
  value: ProviderType;
  label: string;
}

export interface ModelProviderCatalogStatus {
  source: string;
  lastRefreshedAt: string | null;
  providerCount: number;
  modelCount: number;
}

export interface ModelProviderCatalogProvider {
  providerType: string;
  displayName: string;
  defaultUrl: string | null;
  api: string | null;
  iconPath: string | null;
  modelsDevProviderId: string | null;
  supportedTaskTypes: TaskType[];
  modelCounts: Partial<Record<TaskType, number>>;
}

export interface ModelProviderCatalogModel extends AvailableModel {
  taskType: TaskType;
}

export interface ModelProviderCatalogModelsResponse {
  provider: ModelProviderCatalogProvider;
  models: ModelProviderCatalogModel[];
}
