import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Box,
  Dialog,
  Flex,
  Button,
  Text,
  TextField,
  TextArea,
  Separator,
} from "@radix-ui/themes";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useForm, Controller, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";

import type {
  AvailableModel,
  Model,
  ModelCreateRequest,
  ModelProvider,
  ModelUpdateRequest,
  TaskType,
} from "@/lib/model.types";
import { ModelIdSelect } from "@/components/model-id-select";
import { LabeledSelect } from "@/components/select";
import { TagInput } from "@/components/tag-input";
import {
  fetchModelProviderCatalogModels,
  fetchProviders,
  fetchProviderModels,
  fetchTags,
} from "../lib/model-api";
import {
  resolveProviderCatalogType,
  resolveProviderDisplayName,
  supportsEmbeddingDimensions,
} from "../lib/provider-utils";
import { AdvancedParamsSection } from "./advanced-params-section";

// 先定义 schema 和类型，以便在 ModelParamField 中使用
const modelSchema = z.object({
  name: z.string().min(1, "nameRequired"),
  taskType: z.enum(["llm", "embedding", "rerank"]),
  providerId: z.string().min(1, "providerRequired"),
  modelId: z.string().min(1, "modelIdRequired"),
  remark: z.string().optional(),
  tags: z.array(z.string()).optional(),
  temperature: z.number().min(0).max(2).nullable().optional(),
  topP: z.number().min(0).max(1).nullable().optional(),
  topK: z.number().min(0).nullable().optional(),
  minP: z.number().min(0).max(1).nullable().optional(),
  topA: z.number().min(0).max(1).nullable().optional(),
  frequencyPenalty: z.number().min(-2).max(2).nullable().optional(),
  presencePenalty: z.number().min(-2).max(2).nullable().optional(),
  repetitionPenalty: z.number().min(0).max(2).nullable().optional(),
  maxTokens: z.number().min(-1).nullable().optional(),
  contextLength: z.number().min(1).nullable().optional(),
  deepseekReasoningEffort: z.enum(["high", "max"]),
  deepseekThinkingType: z.enum(["enabled", "disabled"]),
  dimensions: z.number().min(1).max(4096).nullable().optional(),
});

type ModelFormData = z.infer<typeof modelSchema>;

interface ModelFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  model?: Model;
  onSubmit: (data: ModelCreateRequest | ModelUpdateRequest) => Promise<void>;
  isSubmitting: boolean;
}

export function ModelFormDialog({
  open,
  onOpenChange,
  model,
  onSubmit,
  isSubmitting,
}: ModelFormDialogProps) {
  const { t } = useTranslation();
  const isEditing = !!model;

  const [availableModels, setAvailableModels] = useState<AvailableModel[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsError, setModelsError] = useState<string>("");
  const [modelOptionsSource, setModelOptionsSource] = useState<
    "catalog" | "remote" | null
  >(null);

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
      tags: [],
      temperature: null,
      topP: null,
      topK: null,
      minP: null,
      topA: null,
      frequencyPenalty: null,
      presencePenalty: null,
      repetitionPenalty: null,
      maxTokens: null,
      contextLength: 128000,
      deepseekReasoningEffort: "high",
      deepseekThinkingType: "enabled",
      dimensions: null,
    },
  });

  // 当对话框打开或模型改变时，重置表单值
  useEffect(() => {
    if (open) {
      if (model) {
        // 编辑模式：回填所有值
        reset({
          name: model.name || "",
          taskType: (model.taskType as TaskType) || "llm",
          providerId: model.providerId || "",
          modelId: model.modelId || "",
          remark: model.remark || "",
          tags: model.tags || [],
          temperature: model.temperature ?? null,
          topP: model.topP ?? null,
          topK: model.topK ?? null,
          minP: model.minP ?? null,
          topA: model.topA ?? null,
          frequencyPenalty: model.frequencyPenalty ?? null,
          presencePenalty: model.presencePenalty ?? null,
          repetitionPenalty: model.repetitionPenalty ?? null,
          maxTokens: model.maxTokens ?? null,
          contextLength: model.contextLength ?? 128000,
          deepseekReasoningEffort: model.deepseekReasoningEffort ?? "high",
          deepseekThinkingType: model.deepseekThinkingType ?? "enabled",
          dimensions: model.dimensions ?? null,
        });
      } else {
        // 新建模式：重置为空
        reset({
          name: "",
          taskType: "llm" as TaskType,
          providerId: "",
          modelId: "",
          remark: "",
          tags: [],
          temperature: null,
          topP: null,
          topK: null,
          minP: null,
          topA: null,
          frequencyPenalty: null,
          presencePenalty: null,
          repetitionPenalty: null,
          maxTokens: null,
          contextLength: 128000,
          deepseekReasoningEffort: "high",
          deepseekThinkingType: "enabled",
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
  // 获取提供商列表
  const { data: providers } = useQuery({
    queryKey: ["model-providers"],
    queryFn: fetchProviders,
    staleTime: 5 * 60 * 1000,
  });

  // 获取已使用的标签
  const { data: existingTags } = useQuery({
    queryKey: ["model-tags"],
    queryFn: fetchTags,
    staleTime: 5 * 60 * 1000,
  });

  // 根据任务类型过滤提供商（openai-compatible始终显示）
  const filteredProviders = useMemo(() => {
    if (!providers) return [];
    return providers.filter(
      (p) =>
        p.providerType === "openai-compatible" ||
        p.supportedTaskTypes?.includes(taskType as TaskType)
    );
  }, [providers, taskType]);

  const selectedProvider = useMemo(
    () => providers?.find((p) => p.id === providerId),
    [providers, providerId]
  );
  const isDeepSeekProvider = selectedProvider?.providerType === "deepseek";
  const selectedCatalogProviderType = useMemo(
    () => (selectedProvider ? resolveProviderCatalogType(selectedProvider) : null),
    [selectedProvider]
  );
  const selectedProviderSupportsEmbeddingDimensions = useMemo(
    () =>
      selectedProvider
        ? supportsEmbeddingDimensions(selectedProvider.providerType)
        : false,
    [selectedProvider]
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
        const result = await fetchModelProviderCatalogModels(
          catalogProviderType,
          currentTaskType
        );
        setAvailableModels(result.models);
      } catch (error) {
        setAvailableModels([]);
        setModelsError(error instanceof Error ? error.message : "加载模型列表失败");
      } finally {
        setLoadingModels(false);
      }
    },
    []
  );

  // 加载提供商的模型列表
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
          // 显示后端返回的错误信息
          setModelsError(result.message || "获取模型列表失败");
        }
      } catch (error) {
        console.error("Failed to load models:", error);
        setAvailableModels([]);
        // 显示网络错误或其他异常
        setModelsError(error instanceof Error ? error.message : "网络请求失败");
      } finally {
        setLoadingModels(false);
      }
    },
    [providers]
  );

  const handleRefreshRemoteModels = useCallback(() => {
    if (!providerId) {
      return;
    }

    void loadModelsForProvider(providerId, taskType as TaskType);
  }, [loadModelsForProvider, providerId, taskType]);

  // 提供商或任务类型变化时，使用 catalog 模型作为默认候选来源
  useEffect(() => {
    if (!open || !selectedProvider) {
      return;
    }

    queueMicrotask(() => {
      void loadCatalogModelsForProvider(selectedProvider, taskType as TaskType);
    });
  }, [loadCatalogModelsForProvider, open, selectedProvider, taskType]);

  // 当提供商或任务类型改变时，清空当前模型选择
  useEffect(() => {
    if (!providerId) {
      queueMicrotask(() => {
        setValue("modelId", "");
        setAvailableModels([]);
        setModelsError("");
        setModelOptionsSource(null);
      });
      return;
    }

    const isInitialEditingValue =
      isEditing &&
      model?.providerId === providerId &&
      model?.taskType === taskType;

    if (!isInitialEditingValue) {
      queueMicrotask(() => {
        setValue("modelId", "");
      });
    }
  }, [isEditing, model?.providerId, model?.taskType, providerId, setValue, taskType]);

  useEffect(() => {
    if (taskType !== "embedding" || !selectedProviderSupportsEmbeddingDimensions) {
      setValue("dimensions", null);
    }
  }, [selectedProviderSupportsEmbeddingDimensions, setValue, taskType]);

  // 处理模型ID选择
  const handleModelIdChange = useCallback(
    (modelId: string, modelName?: string) => {
      setValue("modelId", modelId);
      if (modelName && !getValues("name")) {
        setValue("name", modelName);
      }
    },
    [getValues, setValue]
  );

  // 提交表单
  const onFormSubmit = useCallback(
    async (data: ModelFormData) => {
      // LLM模型的高级参数必须有实际值（使用默认值替代null）
      const requestData = {
        name: data.name,
        task_type: data.taskType,
        provider_id: data.providerId,
        model_id: data.modelId,
        remark: data.remark || "",
        tags: data.tags || [],
        temperature: data.taskType === "llm" ? (data.temperature ?? 0) : null,
        top_p: data.taskType === "llm" ? (data.topP ?? 1) : null,
        top_k: data.taskType === "llm" ? (data.topK ?? 0) : null,
        min_p: data.taskType === "llm" ? (data.minP ?? 0) : null,
        top_a: data.taskType === "llm" ? (data.topA ?? 0) : null,
        frequency_penalty: data.taskType === "llm" ? (data.frequencyPenalty ?? 0) : null,
        presence_penalty: data.taskType === "llm" ? (data.presencePenalty ?? 0) : null,
        repetition_penalty: data.taskType === "llm" ? (data.repetitionPenalty ?? 0) : null,
        max_tokens: data.taskType === "llm" ? (data.maxTokens ?? 0) : null,
        context_length: data.taskType === "llm" ? (data.contextLength ?? 128000) : 128000,
        deepseek_reasoning_effort:
          data.taskType === "llm" && isDeepSeekProvider && data.deepseekThinkingType === "enabled"
            ? data.deepseekReasoningEffort
            : null,
        deepseek_thinking_type:
          data.taskType === "llm" && isDeepSeekProvider ? data.deepseekThinkingType : null,
        dimensions:
          data.taskType === "embedding" && selectedProviderSupportsEmbeddingDimensions
            ? data.dimensions
            : null,
      };

      try {
        await onSubmit(requestData);
        reset();
      } catch (error) {
        console.error("提交失败:", error);
        throw error;
      }
    },
    [isDeepSeekProvider, onSubmit, reset, selectedProviderSupportsEmbeddingDimensions]
  );

  const handleOpenChange = useCallback(
    (newOpen: boolean) => {
      if (!newOpen) {
        reset();
      }
      onOpenChange(newOpen);
    },
    [onOpenChange, reset]
  );

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Content
      maxWidth="600px"
      style={{
        maxHeight: "90vh",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Dialog.Title>
        {isEditing ? t("models.editModel") : t("models.createModel")}
      </Dialog.Title>

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
            console.error("表单验证错误:", errors);
          })}
        >
          <Flex direction="column" gap="4" mt="4">
            {/* 模型名称 */}
            <Flex direction="column" gap="2">
              <Text size="2" weight="medium" color="gray">
                {t("models.name")}{" "}
                <Text color="red" style={{ display: "inline" }}>
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
                  />
                )}
              />
              {errors.name && (
                <Text size="1" color="red">
                  {t(`models.${errors.name.message}`)}
                </Text>
              )}
            </Flex>

            {/* 任务类型 */}
            <Flex direction="column" gap="2">
              <Text size="2" weight="medium" color="gray">
                {t("models.taskType")}{" "}
                <Text color="red" style={{ display: "inline" }}>
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
                    onChange={field.onChange}
                    triggerStyle={{ width: "100%" }}
                    placeholder={t("models.taskTypePlaceholder")}
                  />
                )}
              />
              {errors.taskType && (
                <Text size="1" color="red">
                  {t(`models.${errors.taskType.message}`)}
                </Text>
              )}
            </Flex>

            {/* 提供商 */}
            <Flex direction="column" gap="2">
              <Text size="2" weight="medium" color="gray">
                {t("models.provider")}{" "}
                <Text color="red" style={{ display: "inline" }}>
                  *
                </Text>
              </Text>
              <Controller
                name="providerId"
                control={control}
                render={({ field }) => (
                  <LabeledSelect
                    value={field.value}
                    options={
                      filteredProviders.map((p) => ({
                        value: p.id,
                        label: getProviderOptionLabel(p),
                      }))
                    }
                    onChange={field.onChange}
                    triggerStyle={{ width: "100%" }}
                    placeholder={t("models.providerPlaceholder")}
                  />
                )}
              />
              {errors.providerId && (
                <Text size="1" color="red">
                  {t(`models.${errors.providerId.message}`)}
                </Text>
              )}
              {!providers || providers.length === 0 ? (
                <Text size="1" color="gray">
                  {t("models.noProviders")}
                </Text>
              ) : null}
            </Flex>

            {/* 模型 - 使用高级选择器 */}
            <Flex
              direction="column"
              gap="2"
              style={{
                opacity: isModelSelectionDisabled ? 0.5 : 1,
              }}
            >
              <Text size="2" weight="medium" color="gray">
                {t("models.modelId")}{" "}
                <Text color="red" style={{ display: "inline" }}>
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
                    disabled={isModelSelectionDisabled}
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
                <Text size="1" color="red">
                  {t(`models.${errors.modelId.message}`)}
                </Text>
              )}
              {selectedProvider?.providerType === "openai-compatible" &&
                !selectedCatalogProviderType &&
                !loadingModels && (
                  <Text size="1" color="gray">
                    {t("models.noCatalogMatchHint")}
                  </Text>
                )}
            </Flex>

            {taskType === "embedding" && selectedProviderSupportsEmbeddingDimensions && (
              <Flex direction="column" gap="2">
                <Text size="2" weight="medium" color="gray">
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
                    />
                  )}
                />
                {errors.dimensions && (
                  <Text size="1" color="red">
                    {t(`models.${errors.dimensions.message}`)}
                  </Text>
                )}
                <Text size="1" color="gray">
                  {t("models.dimensionsDesc")}
                </Text>
              </Flex>
            )}

            {/* 备注 */}
            <Flex direction="column" gap="2">
              <Text size="2" weight="medium" color="gray">
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
                  />
                )}
              />
            </Flex>

            {/* 标签 */}
            <Controller
              name="tags"
              control={control}
              render={({ field }) => (
                <TagInput
                  tags={field.value || []}
                  onChange={field.onChange}
                  label={t("models.tags")}
                  placeholder={t("models.tagsPlaceholder")}
                  existingTags={existingTags}
                  existingTagsLabel={existingTags && existingTags.length > 0 ? t("models.existingTags") : undefined}
                />
              )}
            />

            <Separator size="4" />

            {/* 高级参数 - 仅 LLM 模式 */}
            {taskType === "llm" && (
              <AdvancedParamsSection
                control={control}
                getValues={getValues}
                setValue={setValue}
                modelId={model?.id}
                isDeepSeekProvider={isDeepSeekProvider}
              />
            )}

            {/* 操作按钮 */}
            <Flex gap="3" mt="2" justify="end" style={{ flexShrink: 0 }}>
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
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && (
                  <Loader2 size={16} className="animate-spin" />
                )}
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
