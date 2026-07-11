/**
 * Provider Utilities
 *
 * 提供商相关的工具函数。
 */

import type {
  ModelProvider,
  ModelProviderCatalogProvider,
  ProviderOption,
  ProviderType,
  TaskType,
} from "@/lib/model.types";

const ALL_TASK_TYPES: TaskType[] = ["llm", "embedding", "rerank"];

export const SUPPORTED_PROVIDER_TYPES: ProviderType[] = [
  "openai",
  "anthropic",
  "google-genai",
  "ollama",
  "groq",
  "huggingface",
  "mistral",
  "nvidia-ai-endpoints",
  "cohere",
  "openrouter",
  "amazon-nova",
  "deepseek",
  "openai-compatible",
];

const EMBEDDING_DIMENSIONS_SUPPORTED_PROVIDER_TYPES = new Set<ProviderType>([
  "openai",
  "openrouter",
  "openai-compatible",
  "ollama",
  "nvidia-ai-endpoints",
]);

export function isSupportedProviderType(value: string): value is ProviderType {
  return SUPPORTED_PROVIDER_TYPES.includes(value as ProviderType);
}

export function supportsEmbeddingDimensions(providerType: ProviderType): boolean {
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
  const nameMap: Record<ProviderType, string> = {
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

  return nameMap[providerType as ProviderType] ?? providerType;
}

/**
 * 获取提供商的固定 API URL
 */
export function getProviderUrl(
  providerType: ProviderType,
  catalogProviders?: ModelProviderCatalogProvider[],
): string | null {
  if (providerType === "openai-compatible") {
    return null;
  }

  const catalogProvider = catalogProviders?.find(
    (provider) => provider.providerType === providerType,
  );
  return catalogProvider?.defaultUrl ?? null;
}

export function getProviderSelectOptions(
  catalogProviders: ModelProviderCatalogProvider[] | undefined,
  taskType?: TaskType,
): ProviderOption[] {
  const options =
    catalogProviders
      ?.filter((provider) => isSupportedProviderType(provider.providerType))
      .filter((provider) => !taskType || provider.supportedTaskTypes.includes(taskType))
      .map((provider) => ({
        value: provider.providerType as ProviderType,
        label: provider.displayName,
      })) ?? [];

  if (!options.some((option) => option.value === "openai-compatible")) {
    options.push({
      value: "openai-compatible",
      label: getProviderDisplayName("openai-compatible"),
    });
  }

  return options;
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
