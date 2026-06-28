import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import type { ModelIdSelectOption } from "@/components/model-id-select";
import {
  fetchModelProviderCatalogModels,
  fetchModels,
  fetchProviders,
} from "@/features/settings/lib/model-api";
import { resolveProviderCatalogType } from "@/features/settings/lib/provider-utils";

export interface UseLlmModelOptionsResult {
  options: ModelIdSelectOption[];
  isLoading: boolean;
  error: unknown;
}

export function useLlmModelOptions(): UseLlmModelOptionsResult {
  const { data: models, isLoading: isModelsLoading, error: modelsError } = useQuery({
    queryKey: ["models"],
    queryFn: () => fetchModels(),
    staleTime: 5 * 60 * 1000,
  });

  const { data: providers } = useQuery({
    queryKey: ["model-providers"],
    queryFn: fetchProviders,
    staleTime: 5 * 60 * 1000,
  });

  const llmModels = useMemo(
    () => (models ?? []).filter((model) => model.taskType === "llm"),
    [models]
  );

  const catalogProviderTypes = useMemo(() => {
    if (!providers || llmModels.length === 0) return [];
    return Array.from(
      new Set(
        llmModels
          .map((model) => providers.find((provider) => provider.id === model.providerId))
          .map((provider) => (provider ? resolveProviderCatalogType(provider) : null))
          .filter((providerType): providerType is string => Boolean(providerType))
      )
    );
  }, [llmModels, providers]);

  const { data: catalogMetadata } = useQuery({
    queryKey: ["model-provider-catalog", "llm-model-metadata", catalogProviderTypes],
    queryFn: async () => {
      const responses = await Promise.all(
        catalogProviderTypes.map(async (providerType) => {
          const result = await fetchModelProviderCatalogModels(providerType, "llm");
          return [providerType, result.models] as const;
        })
      );
      return new Map(responses);
    },
    enabled: catalogProviderTypes.length > 0,
    staleTime: 5 * 60 * 1000,
  });

  const options = useMemo<ModelIdSelectOption[]>(() => {
    return llmModels.map((model) => {
      const provider = providers?.find((entry) => entry.id === model.providerId);
      const catalogProviderType = provider ? resolveProviderCatalogType(provider) : null;
      const catalogModel = catalogProviderType
        ? catalogMetadata?.get(catalogProviderType)?.find((entry) => entry.id === model.modelId)
        : null;

      return {
        value: model.id,
        id: model.modelId,
        name: model.name,
        taskType: "llm",
        releaseDate: catalogModel?.releaseDate ?? null,
        reasoning: catalogModel?.reasoning ?? null,
        toolCall: catalogModel?.toolCall ?? null,
        inputModalities: catalogModel?.inputModalities ?? [],
        limit: catalogModel?.limit ?? null,
        cost: catalogModel?.cost ?? null,
        contextWindow: catalogModel?.contextWindow ?? model.contextLength,
        inputPricePerMillion: catalogModel?.inputPricePerMillion ?? null,
        outputPricePerMillion: catalogModel?.outputPricePerMillion ?? null,
        cacheReadPricePerMillion: catalogModel?.cacheReadPricePerMillion ?? null,
        source: catalogModel?.source ?? "catalog",
      };
    });
  }, [catalogMetadata, llmModels, providers]);

  return {
    options,
    isLoading: isModelsLoading,
    error: modelsError,
  };
}
