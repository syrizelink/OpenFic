/**
 * Models Settings Component
 *
 * 模型设置面板，管理和配置 AI 模型。
 */

import { useState, useCallback, useMemo } from "react";
import {
  Box,
  Flex,
  Text,
  Button,
  IconButton,
  Badge,
  Tabs,
  Tooltip,
} from "@radix-ui/themes";
import { Plus, Trash2, Edit } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import type {
  Model,
  ModelCreateRequest,
  ModelUpdateRequest,
} from "@/lib/model.types";
import {
  ModelIdSelect,
  type ModelIdSelectOption,
} from "@/components/model-id-select";
import { Spinner } from "@/components";
import {
  CapabilityIcon,
  ContextBadge,
  getModelCapabilityKeys,
  formatContextWindow,
} from "@/components/model-capability-tags";
import {
  fetchModelProviderCatalogModels,
  fetchModels,
  fetchProviders,
  createModel,
  updateModel,
  deleteModel,
} from "../lib/model-api";
import { fetchSettings, updateSettings } from "../lib/settings-api";
import {
  DEFAULT_MODEL_SETTINGS_TAB,
  type ModelSettingsTab,
} from "../lib/settings-route";
import {
  hasSelectableModelProvider,
  resolveProviderCatalogType,
  resolveProviderDisplayName,
} from "../lib/provider-utils";
import { ModelFormDialog } from "./model-form-dialog";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { toast } from "@/components/toast";

interface ModelsSettingsProps {
  activeTab?: ModelSettingsTab;
  onActiveTabChange?: (tab: ModelSettingsTab) => void;
}

export function ModelsSettings({
  activeTab = DEFAULT_MODEL_SETTINGS_TAB,
  onActiveTabChange,
}: ModelsSettingsProps = {}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [formOpen, setFormOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<Model | null>(null);
  const [deletingModel, setDeletingModel] = useState<Model | null>(null);

  // 获取所有模型
  const {
    data: models,
    isLoading: isModelsLoading,
    isFetching: isModelsFetching,
  } = useQuery({
    queryKey: ["models"],
    queryFn: () => fetchModels(),
  });

  // 获取所有提供商（用于显示提供商名称）
  const {
    data: providers,
    isLoading: isProvidersLoading,
    isFetching: isProvidersFetching,
  } = useQuery({
    queryKey: ["model-providers"],
    queryFn: fetchProviders,
  });

  // 获取设置
  const {
    data: settings,
    isLoading: isSettingsLoading,
    isFetching: isSettingsFetching,
  } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  // 更新设置
  const updateSettingsMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success(t("common.saveSuccess"));
    },
  });

  const handleDefaultModelChange = useCallback(
    (value: string) => {
      updateSettingsMutation.mutate({ default_model: value });
    },
    [updateSettingsMutation]
  );

  const handleLightModelChange = useCallback(
    (value: string) => {
      updateSettingsMutation.mutate({ light_model: value });
    },
    [updateSettingsMutation]
  );

  const llmModels = useMemo(
    () => models?.filter((m) => m.taskType === "llm") ?? [],
    [models]
  );
  const llmCatalogProviderTypes = useMemo(() => {
    if (!providers || llmModels.length === 0) {
      return [];
    }

    return Array.from(
      new Set(
        llmModels
          .map((model) => providers.find((provider) => provider.id === model.providerId))
          .map((provider) => (provider ? resolveProviderCatalogType(provider) : null))
          .filter((providerType): providerType is string => Boolean(providerType))
      )
    );
  }, [llmModels, providers]);

  const {
    data: llmCatalogMetadata,
    isLoading: isLlmCatalogMetadataLoading,
    isFetching: isLlmCatalogMetadataFetching,
  } = useQuery({
    queryKey: ["model-provider-catalog", "saved-llm-model-metadata", llmCatalogProviderTypes],
    queryFn: async () => {
      const responses = await Promise.all(
        llmCatalogProviderTypes.map(async (providerType) => {
          const result = await fetchModelProviderCatalogModels(providerType, "llm");
          return [providerType, result.models] as const;
        })
      );

      return new Map(responses);
    },
    enabled: llmCatalogProviderTypes.length > 0,
  });

  const llmModelOptions: ModelIdSelectOption[] = useMemo(() => {
    return llmModels.map((model) => {
      const provider = providers?.find((entry) => entry.id === model.providerId);
      const catalogProviderType = provider ? resolveProviderCatalogType(provider) : null;
      const catalogModel = catalogProviderType
        ? llmCatalogMetadata
            ?.get(catalogProviderType)
            ?.find((entry) => entry.id === model.modelId)
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
  }, [llmCatalogMetadata, llmModels, providers]);

  const llmModelMetadataMap = useMemo(() => {
    const map = new Map<string, ModelIdSelectOption>();
    for (const option of llmModelOptions) {
      map.set(option.value ?? option.id, option);
    }
    return map;
  }, [llmModelOptions]);

  // 创建模型
  const createMutation = useMutation({
    mutationFn: createModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["model-tags"] });
      setFormOpen(false);
      toast.success(t("models.createSuccess"));
    },
    onError: () => {
      toast.error(t("models.createFailed"));
    },
  });

  // 更新模型
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ModelUpdateRequest }) =>
      updateModel(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["model-tags"] });
      setFormOpen(false);
      setEditingModel(null);
      toast.success(t("models.updateSuccess"));
    },
    onError: () => {
      toast.error(t("models.updateFailed"));
    },
  });

  // 删除模型
  const deleteMutation = useMutation({
    mutationFn: deleteModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["model-tags"] });
      setDeletingModel(null);
      toast.success(t("models.deleteSuccess"));
    },
    onError: () => {
      toast.error(t("models.deleteFailed"));
    },
  });

  // 打开创建对话框
  const handleCreate = useCallback(() => {
    setEditingModel(null);
    setFormOpen(true);
  }, []);

  // 打开编辑对话框
  const handleEdit = useCallback((model: Model) => {
    setEditingModel(model);
    setFormOpen(true);
  }, []);

  // 提交表单
  const handleSubmit = useCallback(
    async (data: ModelCreateRequest | ModelUpdateRequest) => {
      if (editingModel) {
        await updateMutation.mutateAsync({
          id: editingModel.id,
          data: data as ModelUpdateRequest,
        });
      } else {
        await createMutation.mutateAsync(data as ModelCreateRequest);
      }
    },
    [editingModel, createMutation, updateMutation]
  );

  // 确认删除
  const handleDelete = useCallback((model: Model) => {
    setDeletingModel(model);
  }, []);

  // 执行删除
  const handleConfirmDelete = useCallback(async () => {
    if (deletingModel) {
      await deleteMutation.mutateAsync(deletingModel.id);
    }
  }, [deletingModel, deleteMutation]);

  // 获取提供商名称
  const getProviderName = useCallback(
    (providerId: string) => {
      const provider = providers?.find((p) => p.id === providerId);
      if (!provider) return providerId;
      return provider.name || resolveProviderDisplayName(provider);
    },
    [providers]
  );

  const filteredModels = models?.filter((m) => m.taskType === activeTab) || [];
  const hasLlmModels = llmModelOptions.length > 0;
  const hasProviders = providers ? hasSelectableModelProvider(providers) : false;
  const isContentLoading =
    isModelsLoading ||
    isModelsFetching ||
    isProvidersLoading ||
    isProvidersFetching ||
    isSettingsLoading ||
    isSettingsFetching ||
      (llmCatalogProviderTypes.length > 0 &&
      (isLlmCatalogMetadataLoading || isLlmCatalogMetadataFetching));

  const handleActiveTabChange = useCallback(
    (value: string) => {
      onActiveTabChange?.(value as ModelSettingsTab);
    },
    [onActiveTabChange]
  );

  if (isContentLoading) {
    return (
      <Flex align="center" justify="center" style={{ height: "100%" }}>
        <Spinner size={18} />
      </Flex>
    );
  }

  return (
    <Box>
      <Flex direction="column" gap="4">
        {/* 描述 */}
        <Text size="2" color="gray">
          {t("models.description")}
        </Text>

        {/* 默认模型 & 轻量模型 */}
        <Flex direction="column" gap="4">
          <Flex direction="column" gap="1" style={{ maxWidth: 400, minWidth: 0 }}>
            <Text size="2" weight="medium">
              {t("models.defaultModel")}
            </Text>
            <Text size="1" color="gray" style={{ marginBottom: "var(--space-1)" }}>
              {t("models.defaultModelDesc")}
            </Text>
            <ModelIdSelect
              value={settings?.defaultModel || ""}
              onChange={handleDefaultModelChange}
              models={llmModelOptions}
              placeholder={hasLlmModels ? t("models.selectModelPlaceholder") : t("models.noModelPlaceholder")}
              editable={false}
              allowCustomValue={false}
              disabled={!hasLlmModels}
              emptyOptionLabel={`（${t("models.selectModelPlaceholder")}）`}
            />
          </Flex>

          <Flex direction="column" gap="1" style={{ maxWidth: 400, minWidth: 0 }}>
            <Text size="2" weight="medium">
              {t("models.lightModel")}
            </Text>
            <Text size="1" color="gray" style={{ marginBottom: "var(--space-1)" }}>
              {t("models.lightModelDesc")}
            </Text>
            <ModelIdSelect
              value={settings?.lightModel || ""}
              onChange={handleLightModelChange}
              models={llmModelOptions}
              placeholder={hasLlmModels ? t("models.selectModelPlaceholder") : t("models.noModelPlaceholder")}
              editable={false}
              allowCustomValue={false}
              disabled={!hasLlmModels}
              emptyOptionLabel={`（${t("models.selectModelPlaceholder")}）`}
            />
          </Flex>
        </Flex>

        {/* 新建按钮 */}
        <Flex>
          <Tooltip content={!hasProviders ? t("models.noProvidersTooltip") : undefined}>
            <span>
              <Button onClick={handleCreate} disabled={!hasProviders}>
                <Plus size={16} />
                {t("models.newModel")}
              </Button>
            </span>
          </Tooltip>
        </Flex>

        {/* Tab导航 */}
        <Tabs.Root
          value={activeTab}
          onValueChange={handleActiveTabChange}
        >
          <Tabs.List>
            <Tabs.Trigger value="llm">{t("models.llmModels")}</Tabs.Trigger>
            <Tabs.Trigger value="embedding">{t("models.embeddingModels")}</Tabs.Trigger>
            <Tabs.Trigger value="rerank">{t("models.rerankModels")}</Tabs.Trigger>
          </Tabs.List>
        </Tabs.Root>

        {/* 模型列表 */}
        {filteredModels.length > 0 ? (
          <Flex direction="column">
            {filteredModels.map((model, index) => (
              <Box key={model.id} className="list-item-hover">
                    <Flex direction="column" gap="3" style={{ padding: "var(--space-4)" }}>
                      <Flex align="center" justify="between">
                        <Flex direction="column" gap="1" style={{ flex: 1 }}>
                          {/* 模型名称 + 元数据标签 */}
                          <Flex align="center" gap="2" wrap="wrap">
                            <Text size="3" weight="medium">
                              {model.name}
                            </Text>
                            {model.isBuiltin ? (
                              <Badge size="1" color="green" variant="soft">
                                {t("models.builtin")}
                              </Badge>
                            ) : null}
                            {(() => {
                              const metadata = llmModelMetadataMap.get(model.id);
                              if (!metadata) return null;
                              const capabilityKeys = getModelCapabilityKeys(metadata);
                              const contextLabel = formatContextWindow(metadata.contextWindow);
                              if (capabilityKeys.length === 0 && !contextLabel) return null;
                              return (
                                <Flex align="center" gap="1">
                                  {capabilityKeys.map((cap) => (
                                    <CapabilityIcon key={cap} capability={cap} />
                                  ))}
                                  {contextLabel ? <ContextBadge label={contextLabel} /> : null}
                                </Flex>
                              );
                            })()}
                          </Flex>

                          {/* 提供商和模型 ID */}
                          <Flex align="center" gap="2">
                            <Text size="2" color="gray">
                              {getProviderName(model.providerId)}
                            </Text>
                            <Text size="2" color="gray">
                              •
                            </Text>
                            <Text size="2" color="gray">
                              {model.modelId}
                            </Text>
                          </Flex>

                          {/* 备注 */}
                          {model.remark && (
                            <Text size="2" color="gray">
                              {model.remark}
                            </Text>
                          )}
                        </Flex>

                        {/* 操作按钮 */}
                        <Flex gap="2">
                          {model.isBuiltin ? null : (
                            <>
                              <IconButton
                                variant="ghost"
                                color="gray"
                                onClick={() => handleEdit(model)}
                              >
                                <Edit size={16} />
                              </IconButton>
                              <IconButton
                                variant="ghost"
                                color="red"
                                onClick={() => handleDelete(model)}
                              >
                                <Trash2 size={16} />
                              </IconButton>
                            </>
                          )}
                        </Flex>
                      </Flex>

                      {/* 标签 */}
                      {model.tags.length > 0 && (
                        <Flex gap="2" wrap="wrap">
                          {model.tags.map((tag) => (
                            <Badge key={tag} size="1" variant="soft">
                              {tag}
                            </Badge>
                          ))}
                        </Flex>
                      )}
                    </Flex>
                    {index < filteredModels.length - 1 && (
                      <Box
                        style={{
                          height: "1px",
                          background: "var(--gray-a4)",
                          marginLeft: "var(--space-4)",
                          marginRight: "var(--space-4)",
                        }}
                      />
                    )}
              </Box>
            ))}
          </Flex>
        ) : (
          <Flex
            direction="column"
            align="center"
            justify="center"
            gap="3"
            style={{ height: 200 }}
          >
            <Text size="2" color="gray">
              {t("models.noModels")}
            </Text>
          </Flex>
        )}
      </Flex>

      {/* 表单对话框 */}
      <ModelFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        model={editingModel || undefined}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
      />

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={!!deletingModel}
        onOpenChange={(open) => !open && setDeletingModel(null)}
        title={t("models.deleteModel")}
        description={t("models.deleteConfirm")}
        onConfirm={handleConfirmDelete}
        confirmText={t("common.delete")}
        cancelText={t("common.cancel")}
        loading={deleteMutation.isPending}
      />
    </Box>
  );
}
