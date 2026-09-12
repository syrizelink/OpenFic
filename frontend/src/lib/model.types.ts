/**
 * Model and Provider Types
 *
 * Definisi tipe terkait model dan penyedia.
 */

/** Jenis penyedia; pengenal penyedia katalog disediakan secara dinamis oleh models.dev. */
export type ProviderType = string;

/** Jenis tugas */
export type TaskType = "llm" | "embedding" | "rerank";

/** Penyedia layanan model */
export interface ModelProvider {
  id: string;
  name: string;
  url: string;
  providerType: ProviderType;
  customHeaderNames: string[];
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

/** Respons penyedia layanan model (format backend) */
export interface ModelProviderResponse {
  id: string;
  name: string;
  url: string;
  provider_type: string;
  custom_header_names?: string[];
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

/** Permintaan pembuatan/pembaruan penyedia (FormData) */
export type ModelProviderFormData = FormData;

/** Permintaan validasi penyedia */
export interface ModelProviderValidateRequest {
  provider_type: string;
  url: string;
  api_key: string;
  custom_headers?: ModelProviderCustomHeader[];
}

export interface ModelProviderCustomHeader {
  key: string;
  value: string;
}

/** Model yang tersedia */
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
  cacheWritePricePerMillion?: number | null;
  source?: "catalog" | "remote";
}

/** Respons validasi penyedia */
export interface ModelProviderValidateResponse {
  success: boolean;
  message: string;
  models: AvailableModel[];
}

/** Model */
export interface Model {
  id: string;
  name: string;
  remark: string;
  providerId: string;
  modelId: string;
  taskType: TaskType;
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
  inputPrice: number;
  outputPrice: number;
  cacheReadPrice: number;
  cacheWritePrice: number;
  dimensions: number | null;
  isBuiltin: boolean;
  createdAt: string;
  updatedAt: string;
}

/** Respons model (format backend) */
export interface ModelResponse {
  id: string;
  name: string;
  remark: string;
  provider_id: string;
  model_id: string;
  task_type: TaskType;
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
  input_price: number;
  output_price: number;
  cache_read_price: number;
  cache_write_price: number;
  dimensions: number | null;
  is_builtin?: boolean;
  created_at: string;
  updated_at: string;
}

/** Permintaan pembuatan model */
export interface ModelCreateRequest {
  name: string;
  provider_id: string;
  model_id: string;
  task_type?: TaskType;
  remark?: string;
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
  input_price?: number | null;
  output_price?: number | null;
  cache_read_price?: number | null;
  cache_write_price?: number | null;
  dimensions?: number | null;
}

/** Permintaan pembaruan model */
export interface ModelUpdateRequest {
  name?: string;
  remark?: string;
  provider_id?: string;
  model_id?: string;
  task_type?: TaskType;
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
  input_price?: number | null;
  output_price?: number | null;
  cache_read_price?: number | null;
  cache_write_price?: number | null;
  dimensions?: number | null;
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
