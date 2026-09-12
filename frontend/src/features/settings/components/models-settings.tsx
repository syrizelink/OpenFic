/**
 * Models Settings Component
 *
 * Panel pengaturan model, mengelola dan mengonfigurasi model AI.
 */

import { Box, Flex, Text, Button, IconButton, Badge, Tabs, Tooltip } from "@radix-ui/themes";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Edit, PlugZap, Plus, Trash2 } from "lucide-react";
import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import { ConfirmDialog } from "@/components/confirm-dialog";
import {
  CapabilityIcon,
  ContextBadge,
  getModelCapabilityKeys,
  formatContextWindow,
} from "@/components/model-capability-tags";
import { ModelIdSelect, type ModelIdSelectOption } from "@/components/model-id-select";
import { toast } from "@/components/toast";
import type { Model, ModelCreateRequest, ModelUpdateRequest } from "@/lib/model.types";

import {
  fetchModelProviderCatalogModels,
  fetchModels,
  fetchProviders,
  createModel,
  updateModel,
  deleteModel,
  validateModel,
} from "../lib/model-api";
import { ProviderIcon } from "../lib/provider-icons";
import {
  hasSelectableModelProvider,
  isCustomProviderType,
  resolveProviderCatalogType,
  resolveProviderDisplayName,
  resolveProviderIconPath,
} from "../lib/provider-utils";
import { fetchSettings, updateSettings } from "../lib/settings-api";
import { DEFAULT_MODEL_SETTINGS_TAB, type ModelSettingsTab } from "../lib/settings-route";
import { AgentSettingsLockNotice } from "./agent-settings-lock-notice";
import { ModelFormDialog } from "./model-form-dialog";

interface ModelsSettingsProps {
  activeTab?: ModelSettingsTab;
  onActiveTabChange?: (tab: ModelSettingsTab) => void;
  isAgentSettingsLocked: boolean;
  isAgentSettingsLockLoading: boolean;
}

export function ModelsSettings({
  activeTab = DEFAULT_MODEL_SETTINGS_TAB,
  onActiveTabChange,
  isAgentSettingsLocked,
  isAgentSettingsLockLoading,
}: ModelsSettingsProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [formOpen, setFormOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<Model | null>(null);
  const [deletingModel, setDeletingModel] = useState<Model | null>(null);
  const [modelValidationStatuses, setModelValidationStatuses] = useState<
    Record<string, "validating" | "success" | "error">
  >({});
  const validationScopeRef = useRef(0);

  useEffect(() => {
    if (!isAgentSettingsLocked) return;
    setFormOpen(false);
    setEditingModel(null);
    setDeletingModel(null);
  }, [isAgentSettingsLocked]);

  useEffect(() => {
    validationScopeRef.current += 1;
    setModelValidationStatuses({});
  }, [activeTab]);

  // Mengambil seluruh model
  const {
    data: models,
    isLoading: isModelsLoading,
    isFetching: isModelsFetching,
  } = useQuery({
    queryKey: ["models"],
    queryFn: () => fetchModels(),
  });

  // Mengambil seluruh penyedia (dipakai untuk menampilkan nama penyedia)
  const {
    data: providers,
    isLoading: isProvidersLoading,
    isFetching: isProvidersFetching,
  } = useQuery({
    queryKey: ["model-providers"],
    queryFn: fetchProviders,
  });

  // Mengambil pengaturan
  const {
    data: settings,
    isLoading: isSettingsLoading,
    isFetching: isSettingsFetching,
  } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  // Memperbarui pengaturan
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
    [updateSettingsMutation],
  );

  const handleLightModelChange = useCallback(
    (value: string) => {
      updateSettingsMutation.mutate({ light_model: value });
    },
    [updateSettingsMutation],
  );

  const llmModels = useMemo(() => models?.filter((m) => m.taskType === "llm") ?? [], [models]);
  const llmCatalogProviderTypes = useMemo(() => {
    if (!providers || llmModels.length === 0) {
      return [];
    }

    return Array.from(
      new Set(
        llmModels
          .map((model) => providers.find((provider) => provider.id === model.providerId))
          .map((provider) => (provider ? resolveProviderCatalogType(provider) : null))
          .filter((providerType): providerType is string => Boolean(providerType)),
      ),
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
        }),
      );

      return new Map(responses);
    },
    enabled: llmCatalogProviderTypes.length > 0,
  });

  const llmModelOptions: ModelIdSelectOption[] = useMemo(() => {
    return llmModels.map((model) => {
      const provider = providers?.find((entry) => entry.id === model.providerId);
      const catalogProviderType = provider ? resolveProviderCatalogType(provider) : null;
      const providerIconPath = provider ? resolveProviderIconPath(provider) : null;
      const catalogModel = catalogProviderType
        ? llmCatalogMetadata?.get(catalogProviderType)?.find((entry) => entry.id === model.modelId)
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
        inputPricePerMillion:
          catalogModel?.inputPricePerMillion ?? (model.inputPrice > 0 ? model.inputPrice : null),
        outputPricePerMillion:
          catalogModel?.outputPricePerMillion ?? (model.outputPrice > 0 ? model.outputPrice : null),
        cacheReadPricePerMillion:
          catalogModel?.cacheReadPricePerMillion ??
          (model.cacheReadPrice > 0 ? model.cacheReadPrice : null),
        cacheWritePricePerMillion:
          catalogModel?.cacheWritePricePerMillion ??
          (model.cacheWritePrice > 0 ? model.cacheWritePrice : null),
        source: catalogModel?.source ?? "catalog",
        providerIconPath,
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

  // Membuat model
  const createMutation = useMutation({
    mutationFn: createModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      setFormOpen(false);
      toast.success(t("models.createSuccess"));
    },
    onError: () => {
      toast.error(t("models.createFailed"));
    },
  });

  // Memperbarui model
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ModelUpdateRequest }) => updateModel(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      setFormOpen(false);
      setEditingModel(null);
      toast.success(t("models.updateSuccess"));
    },
    onError: () => {
      toast.error(t("models.updateFailed"));
    },
  });

  // Menghapus model
  const deleteMutation = useMutation({
    mutationFn: deleteModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      setDeletingModel(null);
      toast.success(t("models.deleteSuccess"));
    },
    onError: () => {
      toast.error(t("models.deleteFailed"));
    },
  });

  // Membuka dialog pembuatan
  const handleCreate = useCallback(() => {
    setEditingModel(null);
    setFormOpen(true);
  }, []);

  // Membuka dialog penyuntingan
  const handleEdit = useCallback((model: Model) => {
    setEditingModel(model);
    setFormOpen(true);
  }, []);

  const handleValidateModel = useCallback(
    async (model: Model) => {
      const validationScope = validationScopeRef.current;
      setModelValidationStatuses((statuses) => ({
        ...statuses,
        [model.id]: "validating",
      }));

      try {
        const result = await validateModel(model.id);
        if (validationScope !== validationScopeRef.current) return;

        if (result.success) {
          setModelValidationStatuses((statuses) => ({
            ...statuses,
            [model.id]: "success",
          }));
          toast.success(t("models.validateModelSuccess"));
          return;
        }

        setModelValidationStatuses((statuses) => ({
          ...statuses,
          [model.id]: "error",
        }));
        toast.error(t("models.validateModelFailed"));
      } catch {
        if (validationScope !== validationScopeRef.current) return;

        setModelValidationStatuses((statuses) => ({
          ...statuses,
          [model.id]: "error",
        }));
        toast.error(t("models.validateModelFailed"));
      }
    },
    [t],
  );

  // Mengirim formulir
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
    [editingModel, createMutation, updateMutation],
  );

  // Mengonfirmasi penghapusan
  const handleDelete = useCallback((model: Model) => {
    setDeletingModel(model);
  }, []);

  // Menjalankan penghapusan
  const handleConfirmDelete = useCallback(async () => {
    if (deletingModel) {
      await deleteMutation.mutateAsync(deletingModel.id);
    }
  }, [deletingModel, deleteMutation]);

  // Mengambil nama penyedia
  const getProviderName = useCallback(
    (providerId: string) => {
      const provider = providers?.find((p) => p.id === providerId);
      if (!provider) return providerId;
      return provider.name || resolveProviderDisplayName(provider);
    },
    [providers],
  );

  const getProviderIcon = useCallback(
    (providerId: string) => {
      const provider = providers?.find((entry) => entry.id === providerId);
      if (!provider || isCustomProviderType(provider.providerType)) {
        return null;
      }

      const iconPath = resolveProviderIconPath(provider) || provider.catalogMatch?.iconPath;

      if (iconPath) {
        return (
          <ProviderIcon
            iconPath={iconPath}
            size={16}
          />
        );
      }

      return null;
    },
    [providers],
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
    isAgentSettingsLockLoading ||
    (llmCatalogProviderTypes.length > 0 &&
      (isLlmCatalogMetadataLoading || isLlmCatalogMetadataFetching));

  const handleActiveTabChange = useCallback(
    (value: string) => {
      onActiveTabChange?.(value as ModelSettingsTab);
    },
    [onActiveTabChange],
  );

  if (isContentLoading) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ height: "100%" }}
      >
        <Spinner size={18} />
      </Flex>
    );
  }

  return (
    <Box>
      <AgentSettingsLockNotice isLocked={isAgentSettingsLocked} />
      <Flex
        direction="column"
        gap="4"
      >
        {/* Deskripsi */}
        <Text
          size="2"
          color="gray"
        >
          {t("models.description")}
        </Text>

        {/* Model bawaan & model ringan */}
        <Flex
          direction="column"
          gap="4"
        >
          <Flex
            direction="column"
            gap="1"
            style={{ maxWidth: 400, minWidth: 0 }}
          >
            <Text
              size="2"
              weight="medium"
            >
              {t("models.defaultModel")}
            </Text>
            <Text
              size="1"
              color="gray"
              style={{ marginBottom: "var(--space-1)" }}
            >
              {t("models.defaultModelDesc")}
            </Text>
            <ModelIdSelect
              value={settings?.defaultModel || ""}
              onChange={handleDefaultModelChange}
              models={llmModelOptions}
              placeholder={
                hasLlmModels ? t("models.selectModelPlaceholder") : t("models.noModelPlaceholder")
              }
              editable={false}
              allowCustomValue={false}
              disabled={isAgentSettingsLocked || !hasLlmModels}
              emptyOptionLabel={`（${t("models.selectModelPlaceholder")}）`}
            />
          </Flex>

          <Flex
            direction="column"
            gap="1"
            style={{ maxWidth: 400, minWidth: 0 }}
          >
            <Text
              size="2"
              weight="medium"
            >
              {t("models.lightModel")}
            </Text>
            <Text
              size="1"
              color="gray"
              style={{ marginBottom: "var(--space-1)" }}
            >
              {t("models.lightModelDesc")}
            </Text>
            <ModelIdSelect
              value={settings?.lightModel || ""}
              onChange={handleLightModelChange}
              models={llmModelOptions}
              placeholder={
                hasLlmModels ? t("models.selectModelPlaceholder") : t("models.noModelPlaceholder")
              }
              editable={false}
              allowCustomValue={false}
              disabled={isAgentSettingsLocked || !hasLlmModels}
              emptyOptionLabel={`（${t("models.selectModelPlaceholder")}）`}
            />
          </Flex>
        </Flex>

        {/* Tombol buat baru */}
        <Flex>
          <Button
            onClick={handleCreate}
            disabled={isAgentSettingsLocked || !hasProviders}
          >
            <Plus size={16} />
            {t("models.newModel")}
          </Button>
        </Flex>

        {/* Navigasi Tab */}
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

        {/* Daftar model */}
        {filteredModels.length > 0 ? (
          <Flex direction="column">
            {filteredModels.map((model, index) => (
              <Box
                key={model.id}
                className="list-item-hover"
              >
                <Flex
                  direction="column"
                  gap="3"
                  style={{ padding: "var(--space-4)" }}
                >
                  <Flex
                    align="center"
                    justify="between"
                  >
                    <Flex
                      direction="column"
                      gap="1"
                      style={{ flex: 1 }}
                    >
                      {/* Nama model + label metadata */}
                      <Flex
                        align="center"
                        gap="2"
                        wrap="wrap"
                      >
                        <Text
                          size="3"
                          weight="medium"
                        >
                          {model.name}
                        </Text>
                        {model.isBuiltin ? (
                          <Badge
                            size="1"
                            color="green"
                            variant="soft"
                          >
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
                            <Flex
                              align="center"
                              gap="1"
                            >
                              {capabilityKeys.map((cap) => (
                                <CapabilityIcon
                                  key={cap}
                                  capability={cap}
                                />
                              ))}
                              {contextLabel ? <ContextBadge label={contextLabel} /> : null}
                            </Flex>
                          );
                        })()}
                      </Flex>

                      {/* Penyedia dan ID model */}
                      <Flex
                        align="center"
                        gap="2"
                      >
                        <Flex
                          align="center"
                          gap="1"
                        >
                          {getProviderIcon(model.providerId)}
                          <Text
                            size="2"
                            color="gray"
                          >
                            {getProviderName(model.providerId)}
                          </Text>
                        </Flex>
                        <Text
                          size="2"
                          color="gray"
                        >
                          •
                        </Text>
                        <Text
                          size="2"
                          color="gray"
                        >
                          {model.modelId}
                        </Text>
                      </Flex>

                      {/* Catatan */}
                      {model.remark && (
                        <Text
                          size="2"
                          color="gray"
                        >
                          {model.remark}
                        </Text>
                      )}
                    </Flex>

                    {/* Tombol tindakan */}
                    <Flex gap="2">
                      {model.taskType === "llm" ? (
                        <Tooltip content={t("models.validateModel")}>
                          <IconButton
                            variant="ghost"
                            color={
                              modelValidationStatuses[model.id] === "success"
                                ? "green"
                                : modelValidationStatuses[model.id] === "error"
                                  ? "red"
                                  : "gray"
                            }
                            onClick={() => void handleValidateModel(model)}
                            disabled={
                              isAgentSettingsLocked ||
                              modelValidationStatuses[model.id] === "validating"
                            }
                            aria-label={t("models.validateModel")}
                          >
                            <PlugZap size={16} />
                          </IconButton>
                        </Tooltip>
                      ) : null}
                      {model.isBuiltin ? null : (
                        <>
                          <Tooltip content={t("models.editModel")}>
                            <IconButton
                              variant="ghost"
                              color="gray"
                              onClick={() => handleEdit(model)}
                              disabled={isAgentSettingsLocked}
                              aria-label={t("models.editModel")}
                            >
                              <Edit size={16} />
                            </IconButton>
                          </Tooltip>
                          <Tooltip content={t("models.deleteModel")}>
                            <IconButton
                              variant="ghost"
                              color="red"
                              onClick={() => handleDelete(model)}
                              disabled={isAgentSettingsLocked}
                              aria-label={t("models.deleteModel")}
                            >
                              <Trash2 size={16} />
                            </IconButton>
                          </Tooltip>
                        </>
                      )}
                    </Flex>
                  </Flex>
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
            <Text
              size="2"
              color="gray"
            >
              {t("models.noModels")}
            </Text>
          </Flex>
        )}
      </Flex>

      {/* Dialog formulir */}
      <ModelFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        model={editingModel || undefined}
        models={models ?? []}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        isAgentSettingsLocked={isAgentSettingsLocked}
      />

      {/* Dialog konfirmasi penghapusan */}
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
