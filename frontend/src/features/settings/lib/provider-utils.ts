/**
 * Provider Utilities
 *
 * 提供商相关的工具函数。
 */

import type {
  ModelProvider,
  ModelProviderCatalogProvider,
  ProviderType,
  TaskType,
} from "@/lib/model.types";

const ALL_TASK_TYPES: TaskType[] = ["llm", "embedding", "rerank"];

const EMBEDDING_DIMENSIONS_SUPPORTED_PROVIDER_TYPES = new Set<ProviderType>([
  "openai",
  "openrouter",
  "openai-compatible",
  "ollama",
  "nvidia-ai-endpoints",
]);

export function supportsEmbeddingDimensions(providerType: string): boolean {
  return EMBEDDING_DIMENSIONS_SUPPORTED_PROVIDER_TYPES.has(providerType);
}

export function isSelectableModelProviderForTask(
  provider: Pick<ModelProvider, "providerType" | "supportedTaskTypes" | "isBuiltin">,
  taskType: TaskType,
): boolean {
  if (provider.isBuiltin) {
    return false;
  }

  return (
    provider.providerType === "openai-compatible" || provider.supportedTaskTypes.includes(taskType)
  );
}

export function hasSelectableModelProvider(
  providers: Array<Pick<ModelProvider, "providerType" | "supportedTaskTypes" | "isBuiltin">>,
): boolean {
  return providers.some((provider) =>
    ALL_TASK_TYPES.some((taskType) => isSelectableModelProviderForTask(provider, taskType)),
  );
}

/**
 * 获取提供商显示名称
 */
export function getProviderDisplayName(providerType: string): string {
  const nameMap: Record<string, string> = {
    openai: "OpenAI",
    anthropic: "Anthropic",
    "google-genai": "Google Generative AI",
    ollama: "Ollama",
    groq: "Groq",
    huggingface: "Hugging Face",
    mistral: "Mistral AI",
    "nvidia-ai-endpoints": "NVIDIA AI Endpoints",
    cohere: "Cohere",
    openrouter: "OpenRouter",
    "amazon-nova": "Amazon Nova",
    deepseek: "DeepSeek",
    "openai-compatible": "OpenAI Compatible",
    builtin: "Builtin",
  };

  return nameMap[providerType] ?? providerType;
}

/**
 * 获取提供商的固定 API URL
 */
export function getProviderUrl(
  providerType: string,
  catalogProviders?: ModelProviderCatalogProvider[],
): string | null {
  if (providerType === "openai-compatible") {
    return null;
  }

  const catalogProvider = catalogProviders?.find(
    (provider) => provider.providerType === providerType,
  );
  return catalogProvider?.api ?? catalogProvider?.defaultUrl ?? null;
}

export function resolveProviderCatalogType(provider: ModelProvider): string | null {
  if (provider.providerType === "openai-compatible") {
    return provider.catalogMatch?.catalogProviderType ?? null;
  }

  return provider.providerType;
}

export function resolveProviderDisplayName(
  provider: Pick<ModelProvider, "providerType" | "catalogMatch">,
): string {
  return provider.catalogMatch?.displayName || getProviderDisplayName(provider.providerType);
}

export function resolveProviderIconPath(provider: Pick<ModelProvider, "iconPath">): string | null {
  return provider.iconPath;
}
