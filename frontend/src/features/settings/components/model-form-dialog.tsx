import { zodResolver } from "@hookform/resolvers/zod";
import { Box, Dialog, Flex, Button, Text, TextField, TextArea, Separator } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useForm, Controller, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { Spinner } from "@/components";
import { ModelIdSelect } from "@/components/model-id-select";
import { LabeledSelect } from "@/components/select";
import type {
  AvailableModel,
  Model,
  ModelCreateRequest,
  ModelProvider,
  ModelUpdateRequest,
  TaskType,
} from "@/lib/model.types";

import {
  fetchModelProviderCatalogModels,
  fetchProviders,
  fetchProviderModels,
} from "../lib/model-api";
import {
  isSelectableModelProvider,
  isCustomProviderType,
  resolveProviderCatalogType,
  resolveProviderDisplayName,
  supportsEmbeddingDimensions,
} from "../lib/provider-utils";
import { AdvancedParamsSection } from "./advanced-params-section";
import { ModelMetadataSection } from "./model-metadata-section";

// Definisikan schema dan tipenya lebih dahulu agar bisa dipakai di ModelParamField
const modelSchema = z.object({
  name: z.string().min(1, "nameRequired"),
  taskType: z.enum(["llm", "embedding", "rerank"]),
  providerId: z.string().min(1, "providerRequired"),
  modelId: z.string().min(1, "modelIdRequired"),
  remark: z.string().optional(),
  temperature: z.number().min(0).max(2),
  topP: z.number().min(0).max(1),
  topK: z.number().int().min(0).max(128),
  minP: z.number().min(0).max(1),
  topA: z.number().min(0).max(1),
  frequencyPenalty: z.number().min(-2).max(2),
  presencePenalty: z.number().min(-2).max(2),
  repetitionPenalty: z.number().min(0).max(2),
  maxTokens: z.number().min(1).nullable().optional(),
  contextLength: z.number().int().min(0).max(2000000),
  inputPrice: z.number().min(0),
  outputPrice: z.number().min(0),
  cacheReadPrice: z.number().min(0),
  cacheWritePrice: z.number().min(0),
  dimensions: z.number().min(1).max(4096).nullable().optional(),
});

type ModelFormData = z.infer<typeof modelSchema>;

interface ModelFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  model?: Model;
  models: Model[];
  onSubmit: (data: ModelCreateRequest | ModelUpdateRequest) => Promise<void>;
  isSubmitting: boolean;
  isAgentSettingsLocked: boolean;
}

export function ModelFormDialog({
  open,
  onOpenChange,
  model,
  models,
  onSubmit,
  isSubmitting,
  isAgentSettingsLocked,
}: ModelFormDialogProps) {
  const { t } = useTranslation();
  const isEditing = !!model;

  const [availableModels, setAvailableModels] = useState<AvailableModel[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsError, setModelsError] = useState<string>("");
  const [modelOptionsSource, setModelOptionsSource] = useState<"catalog" | "remote" | null>(null);

  const {
    control,
    handleSubmit,
    formState: { errors },
    getValues,
    setValue,
    reset,
  } = useForm<ModelFormData>({
    resolver: zodResolver(modelSchema),
    defaultValues: {
      name: "",
      taskType: "llm" as TaskType,
      providerId: "",
      modelId: "",
      remark: "",
      temperature: 1,
      topP: 1,
      topK: 0,
      minP: 0,
      topA: 0,
      frequencyPenalty: 0,
      presencePenalty: 0,
      repetitionPenalty: 1,
      maxTokens: null,
      contextLength: 128000,
      inputPrice: 0,
      outputPrice: 0,
      cacheReadPrice: 0,
      cacheWritePrice: 0,
      dimensions: null,
    },
  });

  // Mereset nilai formulir saat dialog dibuka atau model berubah
  useEffect(() => {
    if (open) {
      if (model) {
        // Mode sunting: mengisi kembali seluruh nilai
        reset({
          name: model.name || "",
          taskType: (model.taskType as TaskType) || "llm",
          providerId: model.providerId || "",
          modelId: model.modelId || "",
          remark: model.remark || "",
          temperature: model.temperature ?? 1,
          topP: model.topP ?? 1,
          topK: model.topK ?? 0,
          minP: model.minP ?? 0,
          topA: model.topA ?? 0,
          frequencyPenalty: model.frequencyPenalty ?? 0,
          presencePenalty: model.presencePenalty ?? 0,
          repetitionPenalty: model.repetitionPenalty ?? 1,
          maxTokens: model.maxTokens ?? null,
          contextLength: model.contextLength ?? 128000,
          inputPrice: model.inputPrice ?? 0,
          outputPrice: model.outputPrice ?? 0,
          cacheReadPrice: model.cacheReadPrice ?? 0,
          cacheWritePrice: model.cacheWritePrice ?? 0,
          dimensions: model.dimensions ?? null,
        });
      } else {
        // Mode buat baru: direset menjadi kosong
        reset({
          name: "",
          taskType: "llm" as TaskType,
          providerId: "",
          modelId: "",
          remark: "",
          temperature: 1,
          topP: 1,
          topK: 0,
          minP: 0,
          topA: 0,
          frequencyPenalty: 0,
          presencePenalty: 0,
          repetitionPenalty: 1,
          maxTokens: null,
          contextLength: 128000,
          inputPrice: 0,
          outputPrice: 0,
          cacheReadPrice: 0,
          cacheWritePrice: 0,
          dimensions: null,
        });
      }
    } else {
      reset();
      queueMicrotask(() => {
        setAvailableModels([]);
        setLoadingModels(false);
        setModelsError("");
        setModelOptionsSource(null);
      });
    }
  }, [open, model, reset]);

  const providerId = useWatch({ control, name: "providerId" });
  const taskType = useWatch({ control, name: "taskType" });
  const name = useWatch({ control, name: "name" });
  const hasDuplicateName = models.some((entry) => entry.id !== model?.id && entry.name === name);
  // Mengambil daftar penyedia
  const { data: providers } = useQuery({
    queryKey: ["model-providers"],
    queryFn: fetchProviders,
    staleTime: 5 * 60 * 1000,
  });

  // Katalog model mungkin tidak memuat jenis tugas yang sebenarnya didukung, jadi hanya penyedia bawaan yang dikecualikan.
  const filteredProviders = useMemo(() => {
    if (!providers) return [];
    return providers.filter(isSelectableModelProvider);
  }, [providers]);

  const selectedProvider = useMemo(
    () => providers?.find((p) => p.id === providerId),
    [providers, providerId],
  );
  const selectedCatalogProviderType = useMemo(
    () => (selectedProvider ? resolveProviderCatalogType(selectedProvider) : null),
    [selectedProvider],
  );
  const selectedProviderSupportsEmbeddingDimensions = useMemo(
    () => (selectedProvider ? supportsEmbeddingDimensions(selectedProvider.providerType) : false),
    [selectedProvider],
  );
  const isModelSelectionDisabled = !providerId;

  const getProviderOptionLabel = useCallback((provider: ModelProvider) => {
    return provider.name || provider.url || resolveProviderDisplayName(provider);
  }, []);

  const loadCatalogModelsForProvider = useCallback(
    async (provider: ModelProvider, currentTaskType: TaskType) => {
      const catalogProviderType = resolveProviderCatalogType(provider);

      setLoadingModels(true);
      setAvailableModels([]);
      setModelsError("");
      setModelOptionsSource("catalog");

      if (!catalogProviderType) {
        setLoadingModels(false);
        return;
      }

      try {
        const result = await fetchModelProviderCatalogModels(catalogProviderType, currentTaskType);
        setAvailableModels(result.models);
      } catch (error) {
        setAvailableModels([]);
        setModelsError(error instanceof Error ? error.message : t("models.loadModelsFailed"));
      } finally {
        setLoadingModels(false);
      }
    },
    [t],
  );

  // Memuat daftar model sebuah penyedia
  const loadModelsForProvider = useCallback(
    async (provId: string, currentTaskType: TaskType) => {
      const provider = providers?.find((p) => p.id === provId);
      if (!provider) return;

      setLoadingModels(true);
      setAvailableModels([]);
      setModelsError("");
      setModelOptionsSource("remote");

      try {
        const result = await fetchProviderModels(provId, currentTaskType);
        if (result.success) {
          setAvailableModels(result.models);
          setModelsError("");
        } else {
          setAvailableModels([]);
          // Menampilkan informasi galat dari backend
          setModelsError(result.message || t("models.fetchModelsFailed"));
        }
      } catch (error) {
        console.error("Failed to load models:", error);
        setAvailableModels([]);
        // Menampilkan galat jaringan atau anomali lain
        setModelsError(error instanceof Error ? error.message : t("models.networkRequestFailed"));
      } finally {
        setLoadingModels(false);
      }
    },
    [providers, t],
  );

  const handleRefreshRemoteModels = useCallback(() => {
    if (!providerId) {
      return;
    }

    void loadModelsForProvider(providerId, taskType as TaskType);
  }, [loadModelsForProvider, providerId, taskType]);

  // Saat penyedia atau jenis tugas berubah, model catalog dipakai sebagai sumber kandidat bawaan
  useEffect(() => {
    if (!open || !selectedProvider) {
      return;
    }

    queueMicrotask(() => {
      void loadCatalogModelsForProvider(selectedProvider, taskType as TaskType);
    });
  }, [loadCatalogModelsForProvider, open, selectedProvider, taskType]);

  // Pilihan model hanya dikosongkan bila formulir pembuatan tidak punya penyedia.
  // reset() pada formulir sunting terpicu sebelum nilai watch tersinkron, jadi ID model tersimpan tidak boleh dikosongkan karenanya.
  useEffect(() => {
    if (!providerId && !isEditing) {
      queueMicrotask(() => {
        setValue("modelId", "");
        setAvailableModels([]);
        setModelsError("");
        setModelOptionsSource(null);
      });
    }
  }, [isEditing, providerId, setValue]);

  const handleProviderChange = useCallback(
    (nextProviderId: string) => {
      setValue("providerId", nextProviderId);
      setValue("modelId", "");
    },
    [setValue],
  );

  const handleTaskTypeChange = useCallback(
    (nextTaskType: string) => {
      setValue("taskType", nextTaskType as TaskType);
      setValue("modelId", "");
    },
    [setValue],
  );

  useEffect(() => {
    if (taskType !== "embedding" || !selectedProviderSupportsEmbeddingDimensions) {
      setValue("dimensions", null);
    }
  }, [selectedProviderSupportsEmbeddingDimensions, setValue, taskType]);

  // Menangani pemilihan ID model
  const handleModelIdChange = useCallback(
    (modelId: string, modelName?: string) => {
      setValue("modelId", modelId);
      if (modelName && !getValues("name")) {
        setValue("name", modelName);
      }
      const catalogModel = availableModels.find((entry) => entry.id === modelId);
      if (
        catalogModel &&
        (catalogModel.source === "catalog" ||
          catalogModel.contextWindow !== null ||
          catalogModel.cost !== null) &&
        typeof catalogModel.contextWindow === "number" &&
        catalogModel.contextWindow >= 0 &&
        catalogModel.contextWindow <= 2000000
      ) {
        setValue("contextLength", catalogModel.contextWindow);
      }
      setValue("inputPrice", catalogModel?.inputPricePerMillion ?? getValues("inputPrice"));
      setValue("outputPrice", catalogModel?.outputPricePerMillion ?? getValues("outputPrice"));
      setValue(
        "cacheReadPrice",
        catalogModel?.cacheReadPricePerMillion ?? getValues("cacheReadPrice"),
      );
      setValue(
        "cacheWritePrice",
        catalogModel?.cacheWritePricePerMillion ?? getValues("cacheWritePrice"),
      );
    },
    [availableModels, getValues, setValue],
  );

  // Mengirim formulir
  const onFormSubmit = useCallback(
    async (data: ModelFormData) => {
      // Parameter lanjutan model LLM harus punya nilai nyata (null diganti nilai bawaan)
      const requestData = {
        name: data.name,
        task_type: data.taskType,
        provider_id: data.providerId,
        model_id: data.modelId,
        remark: data.remark || "",
        temperature: data.taskType === "llm" ? data.temperature : null,
        top_p: data.taskType === "llm" ? data.topP : null,
        top_k: data.taskType === "llm" ? data.topK : null,
        min_p: data.taskType === "llm" ? data.minP : null,
        top_a: data.taskType === "llm" ? data.topA : null,
        frequency_penalty: data.taskType === "llm" ? data.frequencyPenalty : null,
        presence_penalty: data.taskType === "llm" ? data.presencePenalty : null,
        repetition_penalty: data.taskType === "llm" ? data.repetitionPenalty : null,
        max_tokens: data.taskType === "llm" ? data.maxTokens : null,
        context_length: data.taskType === "llm" ? data.contextLength : 128000,
        input_price: data.taskType === "llm" ? data.inputPrice : 0,
        output_price: data.taskType === "llm" ? data.outputPrice : 0,
        cache_read_price: data.taskType === "llm" ? data.cacheReadPrice : 0,
        cache_write_price: data.taskType === "llm" ? data.cacheWritePrice : 0,
        dimensions:
          data.taskType === "embedding" && selectedProviderSupportsEmbeddingDimensions
            ? data.dimensions
            : null,
      };

      try {
        await onSubmit(requestData);
        reset();
      } catch (error) {
        console.error("Gagal mengirim:", error);
        throw error;
      }
    },
    [onSubmit, reset, selectedProviderSupportsEmbeddingDimensions],
  );

  const handleOpenChange = useCallback(
    (newOpen: boolean) => {
      if (!newOpen) {
        reset();
      }
      onOpenChange(newOpen);
    },
    [onOpenChange, reset],
  );

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content
        maxWidth="600px"
        style={{
          maxHeight: "90vh",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <Dialog.Title>{isEditing ? t("models.editModel") : t("models.createModel")}</Dialog.Title>

        <Box
          style={{
            flex: 1,
            overflowY: "auto",
            overflowX: "hidden",
            paddingRight: "var(--space-2)",
            scrollbarWidth: "none", // Firefox
            msOverflowStyle: "none", // IE and Edge
          }}
          className="hide-scrollbar"
        >
          <form
            onSubmit={handleSubmit(onFormSubmit, (errors) => {
              console.error("Galat validasi formulir:", errors);
            })}
          >
            <Flex
              direction="column"
              gap="4"
              mt="4"
            >
              {/* Nama model */}
              <Flex
                direction="column"
                gap="2"
              >
                <Text
                  size="2"
                  weight="medium"
                  color="gray"
                >
                  {t("models.name")}{" "}
                  <Text
                    color="red"
                    style={{ display: "inline" }}
                  >
                    *
                  </Text>
                </Text>
                <Controller
                  name="name"
                  control={control}
                  render={({ field }) => (
                    <TextField.Root
                      {...field}
                      placeholder={t("models.namePlaceholder")}
                      disabled={isAgentSettingsLocked}
                      color={hasDuplicateName ? "red" : undefined}
                    />
                  )}
                />
                {hasDuplicateName && (
                  <Text
                    size="1"
                    color="red"
                  >
                    {t("models.nameDuplicate")}
                  </Text>
                )}
                {errors.name && (
                  <Text
                    size="1"
                    color="red"
                  >
                    {t(`models.${errors.name.message}`)}
                  </Text>
                )}
              </Flex>

              {/* Jenis tugas */}
              <Flex
                direction="column"
                gap="2"
              >
                <Text
                  size="2"
                  weight="medium"
                  color="gray"
                >
                  {t("models.taskType")}{" "}
                  <Text
                    color="red"
                    style={{ display: "inline" }}
                  >
                    *
                  </Text>
                </Text>
                <Controller
                  name="taskType"
                  control={control}
                  render={({ field }) => (
                    <LabeledSelect
                      value={field.value}
                      options={[
                        { value: "llm", label: t("models.taskTypeLLM") },
                        { value: "embedding", label: t("models.taskTypeEmbedding") },
                        { value: "rerank", label: t("models.taskTypeRerank") },
                      ]}
                      onChange={handleTaskTypeChange}
                      triggerStyle={{ width: "100%" }}
                      placeholder={t("models.taskTypePlaceholder")}
                      disabled={isAgentSettingsLocked}
                    />
                  )}
                />
                {errors.taskType && (
                  <Text
                    size="1"
                    color="red"
                  >
                    {t(`models.${errors.taskType.message}`)}
                  </Text>
                )}
              </Flex>

              {/* Penyedia */}
              <Flex
                direction="column"
                gap="2"
              >
                <Text
                  size="2"
                  weight="medium"
                  color="gray"
                >
                  {t("models.provider")}{" "}
                  <Text
                    color="red"
                    style={{ display: "inline" }}
                  >
                    *
                  </Text>
                </Text>
                <Controller
                  name="providerId"
                  control={control}
                  render={({ field }) => (
                    <LabeledSelect
                      value={field.value}
                      options={filteredProviders.map((p) => ({
                        value: p.id,
                        label: getProviderOptionLabel(p),
                      }))}
                      onChange={handleProviderChange}
                      triggerStyle={{ width: "100%" }}
                      placeholder={t("models.providerPlaceholder")}
                      disabled={isAgentSettingsLocked}
                    />
                  )}
                />
                {errors.providerId && (
                  <Text
                    size="1"
                    color="red"
                  >
                    {t(`models.${errors.providerId.message}`)}
                  </Text>
                )}
                {!providers || providers.length === 0 ? (
                  <Text
                    size="1"
                    color="gray"
                  >
                    {t("models.noProviders")}
                  </Text>
                ) : null}
              </Flex>

              {/* Model - memakai pemilih lanjutan */}
              <Flex
                direction="column"
                gap="2"
                style={{
                  opacity: isModelSelectionDisabled ? 0.5 : 1,
                }}
              >
                <Text
                  size="2"
                  weight="medium"
                  color="gray"
                >
                  {t("models.modelId")}{" "}
                  <Text
                    color="red"
                    style={{ display: "inline" }}
                  >
                    *
                  </Text>
                </Text>
                <Controller
                  name="modelId"
                  control={control}
                  render={({ field }) => (
                    <ModelIdSelect
                      value={field.value}
                      onChange={handleModelIdChange}
                      models={availableModels}
                      isLoading={loadingModels}
                      placeholder={t("models.modelIdPlaceholder")}
                      disabled={isAgentSettingsLocked || isModelSelectionDisabled}
                      taskType={taskType as TaskType}
                      error={modelsError}
                      showRefreshButton
                      onRefresh={handleRefreshRemoteModels}
                      isRefreshing={loadingModels && modelOptionsSource === "remote"}
                      refreshDisabled={!providerId || loadingModels}
                    />
                  )}
                />
                {errors.modelId && (
                  <Text
                    size="1"
                    color="red"
                  >
                    {t(`models.${errors.modelId.message}`)}
                  </Text>
                )}
                {selectedProvider &&
                  isCustomProviderType(selectedProvider.providerType) &&
                  !selectedCatalogProviderType &&
                  !loadingModels && (
                    <Text
                      size="1"
                      color="gray"
                    >
                      {t("models.noCatalogMatchHint")}
                    </Text>
                  )}
              </Flex>

              {taskType === "embedding" && selectedProviderSupportsEmbeddingDimensions && (
                <Flex
                  direction="column"
                  gap="2"
                >
                  <Text
                    size="2"
                    weight="medium"
                    color="gray"
                  >
                    {t("models.dimensions")}
                  </Text>
                  <Controller
                    name="dimensions"
                    control={control}
                    render={({ field }) => (
                      <TextField.Root
                        type="number"
                        min={1}
                        max={4096}
                        value={field.value?.toString() || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          field.onChange(val === "" ? null : Number(val));
                        }}
                        placeholder={t("models.dimensionsPlaceholder")}
                        disabled={isAgentSettingsLocked}
                      />
                    )}
                  />
                  {errors.dimensions && (
                    <Text
                      size="1"
                      color="red"
                    >
                      {t(`models.${errors.dimensions.message}`)}
                    </Text>
                  )}
                  <Text
                    size="1"
                    color="gray"
                  >
                    {t("models.dimensionsDesc")}
                  </Text>
                </Flex>
              )}

              {/* Catatan */}
              <Flex
                direction="column"
                gap="2"
              >
                <Text
                  size="2"
                  weight="medium"
                  color="gray"
                >
                  {t("models.remark")}
                </Text>
                <Controller
                  name="remark"
                  control={control}
                  render={({ field }) => (
                    <TextArea
                      {...field}
                      placeholder={t("models.remarkPlaceholder")}
                      rows={2}
                      disabled={isAgentSettingsLocked}
                    />
                  )}
                />
              </Flex>

              <Separator size="4" />

              {/* Parameter lanjutan - hanya mode LLM */}
              {taskType === "llm" && (
                <>
                  <ModelMetadataSection
                    control={control}
                    modelId={model?.id}
                    disabled={isAgentSettingsLocked}
                  />
                  <AdvancedParamsSection
                    control={control}
                    modelId={model?.id}
                  />
                </>
              )}

              {/* Tombol tindakan */}
              <Flex
                gap="3"
                mt="2"
                justify="end"
                style={{ flexShrink: 0 }}
              >
                <Dialog.Close>
                  <Button
                    type="button"
                    variant="soft"
                    color="gray"
                    disabled={isSubmitting}
                  >
                    {t("common.cancel")}
                  </Button>
                </Dialog.Close>
                <Button
                  type="submit"
                  disabled={isAgentSettingsLocked || isSubmitting || hasDuplicateName}
                >
                  {isSubmitting ? <Spinner size={18} /> : null}
                  {isEditing ? t("common.save") : t("common.create")}
                </Button>
              </Flex>
            </Flex>
          </form>
        </Box>
      </Dialog.Content>
    </Dialog.Root>
  );
}
