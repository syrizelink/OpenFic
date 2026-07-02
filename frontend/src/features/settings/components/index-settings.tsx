/**
 * Index Settings Component
 *
 * 索引设置面板：启用范围、嵌入模型、分块参数、自动索引策略、索引信息。
 * 采用与"通用"设置一致的紧凑布局，单选用下拉框。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Button,
  Checkbox,
  Flex,
  Separator,
  Text,
  TextField,
  Badge,
} from "@radix-ui/themes";
import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ModelIdSelect, type ModelIdSelectOption } from "@/components/model-id-select";
import { LabeledSelect } from "@/components/select";
import { ConfirmDialog, Spinner, toast } from "@/components";
import { fetchProjects } from "@/lib/api-client";
import {
  subscribeBackgroundEvents,
  type BackgroundEvent,
} from "@/lib/background-socket";
import {
  getIndexStatusColor,
  OVERALL_INDEX_STATUS_QUERY_KEY,
  useOverallIndexStatus,
  useStartProjectIndex,
  type IndexAutoStrategy,
  type IndexMode,
  type OverallIndexStatus,
  type ProjectIndexStatus,
} from "@/lib/index-status";
import { fetchModels } from "../lib/model-api";
import { fetchSettings, updateSettings } from "../lib/settings-api";
import type { Settings, SettingsUpdateRequest } from "../lib/settings.types";

const FIELD_WIDTH = { width: 240 } as const;
const HINT_STYLE = { marginTop: "var(--space-1)" } as const;

/** 将后端 snake_case 的更新请求映射为前端 camelCase 的 Settings 局部补丁。 */
function patchSettings(
  current: Settings,
  patch: SettingsUpdateRequest
): Settings {
  return {
    ...current,
    language: (patch.language as Settings["language"]) ?? current.language,
    theme: (patch.theme as Settings["theme"]) ?? current.theme,
    fontFamily: patch.font_family ?? current.fontFamily,
    codeFontFamily: patch.code_font_family ?? current.codeFontFamily,
    defaultModel: patch.default_model ?? current.defaultModel,
    lightModel: patch.light_model ?? current.lightModel,
    defaultEmbeddingModel:
      patch.default_embedding_model ?? current.defaultEmbeddingModel,
    indexMode: patch.index_mode ?? current.indexMode,
    indexEnabledProjects:
      patch.index_enabled_projects ?? current.indexEnabledProjects,
    indexChunkSize: patch.index_chunk_size ?? current.indexChunkSize,
    indexChunkOverlap: patch.index_chunk_overlap ?? current.indexChunkOverlap,
    indexAutoStrategy:
      patch.index_auto_strategy ?? current.indexAutoStrategy,
    indexRerankEnabled:
      patch.index_rerank_enabled ?? current.indexRerankEnabled,
    defaultRerankModel:
      patch.default_rerank_model ?? current.defaultRerankModel,
    agentBypassToolApproval:
      patch.agent_bypass_tool_approval ?? current.agentBypassToolApproval,
    agentToolPermissions: patch.agent_tool_permissions
      ? patch.agent_tool_permissions.map((item) => ({
          toolName: item.tool_name,
          mode: item.mode,
        }))
      : current.agentToolPermissions,
  };
}

export function IndexSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const {
    data: settings,
    isLoading: isSettingsLoading,
    isFetching: isSettingsFetching,
  } = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const {
    data: models,
    isLoading: isModelsLoading,
    isFetching: isModelsFetching,
  } = useQuery({
    queryKey: ["models"],
    queryFn: () => fetchModels(),
  });
  const {
    data: projectsData,
    isLoading: isProjectsLoading,
    isFetching: isProjectsFetching,
  } = useQuery({
    queryKey: ["projects", "all-for-index"],
    queryFn: () => fetchProjects({ page: 1, pageSize: 100 }),
  });
  const overall = useOverallIndexStatus(Boolean(settings));

  // 订阅各项目的后台事件，索引任务失败时 toast 报错。
  // index:status 仅携带 failed_count，无法展示具体错误；
  // 索引任务出错会抛出异常使 job 标记为 failed 并发布 background_job_failed
  // 事件（携带 message），这里据此 toast。
  const projectIds = useMemo(
    () => overall.data?.projects.map((p) => p.project_id) ?? [],
    [overall.data?.projects]
  );
  const projectIdsKey = projectIds.join("|");
  useEffect(() => {
    if (projectIds.length === 0) return;
    const subs = projectIds.map((pid) =>
      subscribeBackgroundEvents(pid, (event: BackgroundEvent) => {
        if (
          event.type === "background_job_failed" &&
          event.job_type === "retrieval_chapter_index_batch"
        ) {
          const message =
            typeof event.payload?.message === "string"
              ? event.payload.message
              : t("index.indexFailedUnknown");
          toast.error(t("index.indexFailed", { message }));
        }
      })
    );
    return () => subs.forEach((s) => s.close());
    // projectIdsKey 变化时重新订阅。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectIdsKey, t]);

  const updateSettingsMutation = useMutation({
    mutationFn: updateSettings,
    onMutate: async (patch) => {
      // 乐观更新：立即将补丁合并进缓存，记录前值以便回滚。
      await queryClient.cancelQueries({ queryKey: ["settings"] });
      const previous = queryClient.getQueryData<Settings>(["settings"]);
      if (previous) {
        queryClient.setQueryData<Settings>(["settings"], patchSettings(previous, patch));
      }
      return { previous };
    },
    onError: (_error, _patch, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["settings"], context.previous);
      }
      toast.error(t("common.saveFailed"));
    },
    onSuccess: (savedSettings) => {
      queryClient.setQueryData(["settings"], savedSettings);
      queryClient.invalidateQueries({ queryKey: OVERALL_INDEX_STATUS_QUERY_KEY });
      toast.success(t("common.saveSuccess"));
    },
  });

  const embeddingModelOptions: ModelIdSelectOption[] = useMemo(() => {
    return (models?.filter((m) => m.taskType === "embedding") ?? []).map((model) => ({
      value: model.id,
      id: model.modelId,
      name: model.name,
      taskType: "embedding",
      releaseDate: null,
      reasoning: null,
      toolCall: null,
      inputModalities: [],
      limit: null,
      cost: null,
      contextWindow: model.contextLength,
      inputPricePerMillion: null,
      outputPricePerMillion: null,
      cacheReadPricePerMillion: null,
    }));
  }, [models]);

  const [pendingEmbeddingModelId, setPendingEmbeddingModelId] = useState<string | null>(null);
  const [chunkSize, setChunkSize] = useState<string>(String(settings?.indexChunkSize ?? 800));
  const [chunkOverlap, setChunkOverlap] = useState<string>(
    String(settings?.indexChunkOverlap ?? 100)
  );

  const rerankModelOptions: ModelIdSelectOption[] = useMemo(() => {
    return (models?.filter((m) => m.taskType === "rerank") ?? []).map((model) => ({
      value: model.id,
      id: model.modelId,
      name: model.name,
      taskType: "rerank",
      releaseDate: null,
      reasoning: null,
      toolCall: null,
      inputModalities: [],
      limit: null,
      cost: null,
      contextWindow: model.contextLength,
      inputPricePerMillion: null,
      outputPricePerMillion: null,
      cacheReadPricePerMillion: null,
    }));
  }, [models]);

  const handleRerankEnabledChange = useCallback(
    (enabled: boolean) => {
      updateSettingsMutation.mutate({ index_rerank_enabled: enabled });
    },
    [updateSettingsMutation]
  );

  const handleRerankModelChange = useCallback(
    (value: string) => {
      updateSettingsMutation.mutate({ default_rerank_model: value });
    },
    [updateSettingsMutation]
  );

  // 当服务端分块参数变化时（如被其他端修改），同步本地输入。
  const [lastServerSize, setLastServerSize] = useState<number | undefined>(
    settings?.indexChunkSize
  );
  const [lastServerOverlap, setLastServerOverlap] = useState<number | undefined>(
    settings?.indexChunkOverlap
  );
  if (
    settings &&
    (settings.indexChunkSize !== lastServerSize ||
      settings.indexChunkOverlap !== lastServerOverlap)
  ) {
    setLastServerSize(settings.indexChunkSize);
    setLastServerOverlap(settings.indexChunkOverlap);
    setChunkSize(String(settings.indexChunkSize));
    setChunkOverlap(String(settings.indexChunkOverlap));
  }

  // 分块参数防抖自动保存：输入停止 800ms 后校验并保存。
  const chunkSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    return () => {
      if (chunkSaveTimerRef.current !== null) {
        clearTimeout(chunkSaveTimerRef.current);
        chunkSaveTimerRef.current = null;
      }
    };
  }, []);

  const scheduleChunkSave = useCallback(() => {
    if (chunkSaveTimerRef.current !== null) {
      clearTimeout(chunkSaveTimerRef.current);
    }
    chunkSaveTimerRef.current = setTimeout(() => {
      chunkSaveTimerRef.current = null;
      const size = Number.parseInt(chunkSize, 10);
      const overlap = Number.parseInt(chunkOverlap, 10);
      if (Number.isNaN(size) || size < 1) return;
      if (Number.isNaN(overlap) || overlap < 0 || overlap >= size) return;
      if (size === settings?.indexChunkSize && overlap === settings?.indexChunkOverlap) return;
      updateSettingsMutation.mutate({
        index_chunk_size: size,
        index_chunk_overlap: overlap,
      });
    }, 800);
  }, [chunkSize, chunkOverlap, settings?.indexChunkSize, settings?.indexChunkOverlap, updateSettingsMutation]);

  const modeOptions = useMemo(
    () => [
      { value: "off", label: t("index.enableOff") },
      { value: "all", label: t("index.enableAll") },
      { value: "selected", label: t("index.enableSelected") },
    ],
    [t]
  );
  const autoStrategyOptions = useMemo(
    () => [
      { value: "immediate", label: t("index.autoImmediate") },
      { value: "agent_decided", label: t("index.autoAgentDecided") },
      { value: "off", label: t("index.autoOff") },
    ],
    [t]
  );

  const handleModeChange = useCallback(
    (mode: string) => {
      updateSettingsMutation.mutate({ index_mode: mode as IndexMode });
    },
    [updateSettingsMutation]
  );

  const handleToggleProject = useCallback(
    (projectId: string, enabled: boolean) => {
      const current = settings?.indexEnabledProjects ?? [];
      const next = enabled
        ? Array.from(new Set([...current, projectId]))
        : current.filter((id) => id !== projectId);
      updateSettingsMutation.mutate({ index_enabled_projects: next });
    },
    [settings?.indexEnabledProjects, updateSettingsMutation]
  );

  const handleEmbeddingModelChange = useCallback(
    (value: string) => {
      const current = settings?.defaultEmbeddingModel || "";
      if (current && value !== current) {
        setPendingEmbeddingModelId(value);
        return;
      }
      updateSettingsMutation.mutate({ default_embedding_model: value });
    },
    [settings?.defaultEmbeddingModel, updateSettingsMutation]
  );

  const confirmEmbeddingModelChange = useCallback(() => {
    if (pendingEmbeddingModelId === null) return;
    updateSettingsMutation.mutate({ default_embedding_model: pendingEmbeddingModelId });
    setPendingEmbeddingModelId(null);
  }, [pendingEmbeddingModelId, updateSettingsMutation]);

  const handleAutoStrategyChange = useCallback(
    (strategy: string) => {
      updateSettingsMutation.mutate({
        index_auto_strategy: strategy as IndexAutoStrategy,
      });
    },
    [updateSettingsMutation]
  );

  const isContentLoading =
    isSettingsLoading ||
    isSettingsFetching ||
    isModelsLoading ||
    isModelsFetching ||
    isProjectsLoading ||
    isProjectsFetching ||
    overall.isLoading ||
    overall.isFetching ||
    !settings;

  if (isContentLoading) {
    return (
      <Flex align="center" justify="center" style={{ height: "100%" }}>
        <Spinner size={18} />
      </Flex>
    );
  }

  const modeDescKey =
    settings.indexMode === "off"
      ? "index.enableOffDesc"
      : settings.indexMode === "all"
        ? "index.enableAllDesc"
        : "index.enableSelectedDesc";
  const autoDescKey =
    settings.indexAutoStrategy === "immediate"
      ? "index.autoImmediateDesc"
      : settings.indexAutoStrategy === "agent_decided"
        ? "index.autoAgentDecidedDesc"
        : "index.autoOffDesc";

  return (
    <Box>
      <Flex direction="column" gap="4">
        {/* 启用范围 */}
        <LabeledSelect
          label={t("index.enable")}
          value={settings.indexMode}
          options={modeOptions}
          onChange={handleModeChange}
          disabled={updateSettingsMutation.isPending}
          triggerStyle={FIELD_WIDTH}
        />
        <Text size="1" color="gray" style={HINT_STYLE}>
          {t(modeDescKey)}
        </Text>

        {settings.indexMode === "selected" ? (
          <Flex direction="column" gap="1" style={{ marginTop: "var(--space-1)" }}>
            <Text size="2" weight="medium" color="gray">
              {t("index.selectProjects")}
            </Text>
            {projectsData && projectsData.items.length > 0 ? (
              projectsData.items.map((project) => (
                <Text
                  key={project.id}
                  as="label"
                  size="2"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-2)",
                    padding: "4px 6px",
                    borderRadius: "var(--radius-2)",
                    cursor: updateSettingsMutation.isPending ? "not-allowed" : "pointer",
                  }}
                >
                  <Checkbox
                    checked={settings.indexEnabledProjects.includes(project.id)}
                    disabled={updateSettingsMutation.isPending}
                    onCheckedChange={(checked) =>
                      handleToggleProject(project.id, checked === true)
                    }
                  />
                  {project.title}
                </Text>
              ))
            ) : (
              <Text size="2" color="gray">
                {t("index.noProjects")}
              </Text>
            )}
          </Flex>
        ) : null}

        {/* 嵌入模型 */}
        <Flex direction="column" gap="2" style={{ maxWidth: 240 }}>
          <Text size="2" weight="medium">
            {t("index.embeddingModel")}
          </Text>
          <ModelIdSelect
            value={settings.defaultEmbeddingModel || ""}
            onChange={handleEmbeddingModelChange}
            models={embeddingModelOptions}
            taskType="embedding"
            placeholder={t("index.selectEmbeddingModelPlaceholder")}
            editable={false}
            allowCustomValue={false}
            emptyOptionLabel={`（${t("index.selectEmbeddingModelPlaceholder")}）`}
          />
          <Text size="1" color="gray" style={HINT_STYLE}>
            {t("index.embeddingModelDesc")}
          </Text>
          {!overall.data?.embedding_model_configured ? (
            <Text size="1" color="amber">
              {t("index.infoNotConfigured")}
            </Text>
          ) : null}
        </Flex>

        {/* Rerank 二次排序 */}
        <Flex direction="column" gap="2" style={{ maxWidth: 240 }}>
          <Text
            as="label"
            size="2"
            weight="medium"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
              cursor: updateSettingsMutation.isPending ? "not-allowed" : "pointer",
            }}
          >
            <Checkbox
              checked={settings.indexRerankEnabled}
              disabled={updateSettingsMutation.isPending}
              onCheckedChange={(checked) =>
                handleRerankEnabledChange(checked === true)
              }
            />
            {t("index.rerankEnabled")}
          </Text>
          {settings.indexRerankEnabled ? (
            <>
              <ModelIdSelect
                value={settings.defaultRerankModel || ""}
                onChange={handleRerankModelChange}
                models={rerankModelOptions}
                taskType="rerank"
                placeholder={t("index.selectRerankModelPlaceholder")}
                editable={false}
                allowCustomValue={false}
                disabled={updateSettingsMutation.isPending}
                emptyOptionLabel={`（${t("index.selectRerankModelPlaceholder")}）`}
              />
              {!settings.defaultRerankModel ? (
                <Text size="1" color="amber">
                  {t("index.rerankModelNotConfigured")}
                </Text>
              ) : null}
            </>
          ) : null}
          <Text size="1" color="gray" style={HINT_STYLE}>
            {t("index.rerankEnabledDesc")}
          </Text>
        </Flex>

        {/* 分块参数 */}
        <Flex direction="column" gap="2">
          <Text size="2" weight="medium">
            {t("index.chunkParams")}
          </Text>
          <Flex direction="column" gap="2">
            <Flex direction="column" gap="1" style={{ width: 240 }}>
              <Text size="1" color="gray">
                {t("index.chunkSize")}
              </Text>
              <TextField.Root
                type="number"
                value={chunkSize}
                onChange={(e) => {
                  setChunkSize(e.target.value);
                  scheduleChunkSave();
                }}
                min={1}
                disabled={updateSettingsMutation.isPending}
              />
            </Flex>
            <Flex direction="column" gap="1" style={{ width: 240 }}>
              <Text size="1" color="gray">
                {t("index.chunkOverlap")}
              </Text>
              <TextField.Root
                type="number"
                value={chunkOverlap}
                onChange={(e) => {
                  setChunkOverlap(e.target.value);
                  scheduleChunkSave();
                }}
                min={0}
                disabled={updateSettingsMutation.isPending}
              />
            </Flex>
          </Flex>
          <Text size="1" color="gray" style={HINT_STYLE}>
            {t("index.chunkParamsHint")}
          </Text>
        </Flex>

        {/* 自动索引策略 */}
        <LabeledSelect
          label={t("index.autoStrategy")}
          value={settings.indexAutoStrategy}
          options={autoStrategyOptions}
          onChange={handleAutoStrategyChange}
          disabled={updateSettingsMutation.isPending}
          triggerStyle={FIELD_WIDTH}
        />
        <Text size="1" color="gray" style={HINT_STYLE}>
          {t(autoDescKey)}
        </Text>

        {/* 索引信息 */}
        <Separator size="4" />
        <Flex direction="column" gap="3">
          <Text size="2" weight="medium">
            {t("index.info")}
          </Text>
          <OverallIndexInfo data={overall.data} />
          {overall.data && overall.data.projects.length > 0 ? (
            <Flex direction="column" gap="2">
              {overall.data.projects.map((project) => (
                <ProjectIndexInfoRow key={project.project_id} status={project} />
              ))}
            </Flex>
          ) : (
            <Text size="2" color="gray">
              {t("index.infoEmpty")}
            </Text>
          )}
        </Flex>
      </Flex>

      <ConfirmDialog
        open={pendingEmbeddingModelId !== null}
        onOpenChange={(open) => !open && setPendingEmbeddingModelId(null)}
        title={t("index.embeddingModelChangeTitle")}
        description={t("index.embeddingModelChangeConfirm")}
        onConfirm={confirmEmbeddingModelChange}
        confirmText={t("common.confirm")}
        cancelText={t("common.cancel")}
        confirmColor="blue"
        loading={updateSettingsMutation.isPending}
      />
    </Box>
  );
}

function OverallIndexInfo({ data }: { data: OverallIndexStatus | undefined }) {
  const { t } = useTranslation();
  if (!data) return null;
  const remaining = Math.max(0, data.total_chapters - data.indexed_count);
  return (
    <Flex gap="4" wrap="wrap">
      <InfoStat label={t("index.totalChapters")} value={data.total_chapters} />
      <InfoStat label={t("index.indexed")} value={data.indexed_count} />
      <InfoStat label={t("index.pending")} value={remaining} />
      <InfoStat label={t("index.statusIndexing")} value={data.in_progress_count} />
    </Flex>
  );
}

function InfoStat({ label, value }: { label: string; value: number }) {
  return (
    <Flex direction="column" gap="1">
      <Text size="1" color="gray">
        {label}
      </Text>
      <Text size="3" weight="medium">
        {value}
      </Text>
    </Flex>
  );
}

function ProjectIndexInfoRow({ status }: { status: ProjectIndexStatus }) {
  const { t } = useTranslation();
  const startMutation = useStartProjectIndex(status.project_id);
  const color = getIndexStatusColor(status.status);
  const indexable = Math.max(
    0,
    status.total_chapters - (status.empty_content_count || 0),
  );
  const progressPct =
    indexable > 0 ? Math.round((status.indexed_count / indexable) * 100) : 0;
  const canStart =
    status.enabled &&
    status.status !== "indexing" &&
    status.status !== "disabled" &&
    status.status !== "not_configured" &&
    status.status !== "no_chapters" &&
    status.pending_count > 0;

  return (
    <Flex align="center" justify="between" gap="3" wrap="wrap">
      <Flex direction="column" gap="1" style={{ flex: "1 1 200px", minWidth: 0 }}>
        <Flex align="center" gap="2">
          <Text size="2" weight="medium">
            {status.title || t("index.untitledProject")}
          </Text>
          <Badge size="1" variant="soft" style={{ color }}>
            {t(`index.status.${status.status}` as const)}
          </Badge>
        </Flex>
        <Text size="1" color="gray">
          {t("index.progress", {
            indexed: status.indexed_count,
            total: indexable,
          })}
          {status.pending_count > 0
            ? t("index.progressRemaining", { pending: status.pending_count })
            : ""}
          {status.empty_content_count > 0
            ? t("index.emptyContentHint", { count: status.empty_content_count })
            : ""}
          {indexable > 0 ? ` · ${progressPct}%` : ""}
        </Text>
        {status.last_error ? (
          <Text size="1" color="red" style={{ wordBreak: "break-word" }}>
            {status.last_error}
          </Text>
        ) : null}
      </Flex>
      {status.enabled ? (
        <Button
          size="1"
          variant="soft"
          onClick={() => startMutation.mutate()}
          disabled={startMutation.isPending || !canStart}
        >
          {startMutation.isPending || status.status === "indexing" ? (
            <Spinner size={18} />
          ) : (
            <RefreshCw size={14} />
          )}
          {status.status === "indexing" ? t("index.indexing") : t("index.startIndex")}
        </Button>
      ) : null}
    </Flex>
  );
}
