/**
 * Provider Utilities
 *
 * 提供商相关的工具函数。
 */

import type { ModelProvider, ModelProviderCatalogProvider, ProviderType } from "@/lib/model.types";

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

export function isSelectableModelProvider(provider: Pick<ModelProvider, "isBuiltin">): boolean {
  return !provider.isBuiltin;
}

export function hasSelectableModelProvider(
  providers: Array<Pick<ModelProvider, "isBuiltin">>,
): boolean {
  return providers.some(isSelectableModelProvider);
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
    "anthropic-compatible": "Anthropic Compatible",
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
  if (providerType === "openai-compatible" || providerType === "anthropic-compatible") {
    return null;
  }

  const catalogProvider = catalogProviders?.find(
    (provider) => provider.providerType === providerType,
  );
  return catalogProvider?.api ?? catalogProvider?.defaultUrl ?? null;
}

export function resolveProviderCatalogType(provider: ModelProvider): string | null {
  if (
    provider.providerType === "openai-compatible" ||
    provider.providerType === "anthropic-compatible"
  ) {
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
