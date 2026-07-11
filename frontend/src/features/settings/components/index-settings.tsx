/**
 * Index Settings Component
 *
 * 索引设置面板：启用范围、嵌入模型、分块参数、自动索引策略、索引信息。
 * 采用与"通用"设置一致的紧凑布局，单选用下拉框。
 */

import { Box, Flex } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog, Spinner, toast } from "@/components";
import type { ModelIdSelectOption } from "@/components/model-id-select";
import { fetchProjects } from "@/lib/api-client";
import { subscribeBackgroundEvents, type BackgroundEvent } from "@/lib/background-socket";
import {
  OVERALL_INDEX_STATUS_QUERY_KEY,
  useOverallIndexStatus,
  type IndexAutoStrategy,
  type IndexMode,
  type OverallIndexStatus,
  type ProjectIndexStatus,
} from "@/lib/index-status";

import { fetchModels, fetchProviders } from "../lib/model-api";
import { resolveProviderIconPath } from "../lib/provider-utils";
import { fetchSettings, updateSettings } from "../lib/settings-api";
import type { Settings, SettingsUpdateRequest } from "../lib/settings.types";
import { IndexSettingsGlobalConfig } from "./index-settings-global-config";
import { IndexSettingsOverview } from "./index-settings-overview";
import {
  ProjectIndexList,
  type IndexUnitStatus,
  type ProjectIndexGroup,
} from "./project-index-list";

import "./project-index-list.css";

interface IndexProjectOption {
  id: string;
  title: string;
}

/** 将后端 snake_case 的更新请求映射为前端 camelCase 的 Settings 局部补丁。 */
function patchSettings(current: Settings, patch: SettingsUpdateRequest): Settings {
  return {
    ...current,
    language: (patch.language as Settings["language"]) ?? current.language,
    theme: (patch.theme as Settings["theme"]) ?? current.theme,
    fontFamily: patch.font_family ?? current.fontFamily,
    codeFontFamily: patch.code_font_family ?? current.codeFontFamily,
    defaultModel: patch.default_model ?? current.defaultModel,
    lightModel: patch.light_model ?? current.lightModel,
    defaultEmbeddingModel: patch.default_embedding_model ?? current.defaultEmbeddingModel,
    indexMode: patch.index_mode ?? current.indexMode,
    indexEnabledProjects: patch.index_enabled_projects ?? current.indexEnabledProjects,
    indexChunkSize: patch.index_chunk_size ?? current.indexChunkSize,
    indexChunkOverlap: patch.index_chunk_overlap ?? current.indexChunkOverlap,
    indexAutoStrategy: patch.index_auto_strategy ?? current.indexAutoStrategy,
    indexRerankEnabled: patch.index_rerank_enabled ?? current.indexRerankEnabled,
    defaultRerankModel: patch.default_rerank_model ?? current.defaultRerankModel,
    agentBypassToolApproval: patch.agent_bypass_tool_approval ?? current.agentBypassToolApproval,
    agentToolPermissions: patch.agent_tool_permissions
      ? patch.agent_tool_permissions.map((item) => ({
          toolName: item.tool_name,
          mode: item.mode,
        }))
      : current.agentToolPermissions,
  };
}

function toChapterIndexUnit(status: ProjectIndexStatus): IndexUnitStatus {
  return {
    id: "chapters",
    labelKey: "index.unit.chapters",
    status: status.status,
    total: Math.max(0, status.total_chapters - (status.empty_content_count || 0)),
    indexed: status.indexed_count,
    pending: status.pending_count + status.in_progress_count,
  };
}

function toProjectIndexGroups(data: OverallIndexStatus | undefined): ProjectIndexGroup[] {
  return (
    data?.projects.map((project) => ({
      projectId: project.project_id,
      title: project.title,
      enabled: project.enabled,
      status: project.status,
      units: [toChapterIndexUnit(project)],
    })) ?? []
  );
}

function createOptimisticProjectStatus(
  project: IndexProjectOption,
  embeddingConfigured: boolean,
): ProjectIndexStatus {
  return {
    project_id: project.id,
    enabled: true,
    status: embeddingConfigured ? "no_index" : "not_configured",
    title: project.title,
    total_chapters: 0,
    indexed_count: 0,
    pending_count: 0,
    in_progress_count: 0,
    failed_count: 0,
    empty_content_count: 0,
    last_error: null,
    progress: 0,
  };
}

function patchOverallIndexStatus(
  current: OverallIndexStatus,
  nextSettings: Settings,
  allProjects: IndexProjectOption[],
  embeddingConfigured: boolean,
): OverallIndexStatus {
  const allProjectIds = allProjects.map((project) => project.id);
  const enabledProjectIds =
    nextSettings.indexMode === "off"
      ? []
      : nextSettings.indexMode === "all"
        ? allProjectIds
        : nextSettings.indexEnabledProjects.filter((projectId) =>
            allProjectIds.includes(projectId),
          );

  const projectById = new Map(allProjects.map((project) => [project.id, project]));
  const previousById = new Map(current.projects.map((project) => [project.project_id, project]));

  const projects = enabledProjectIds.flatMap((projectId) => {
    const project = projectById.get(projectId);
    if (!project) return [];

    const previous = previousById.get(projectId);
    if (!previous) {
      return [createOptimisticProjectStatus(project, embeddingConfigured)];
    }

    return [
      {
        ...previous,
        title: project.title,
        enabled: true,
        status: embeddingConfigured ? previous.status : "not_configured",
      },
    ];
  });

  const sum = (select: (project: ProjectIndexStatus) => number) =>
    projects.reduce((total, project) => total + select(project), 0);

  return {
    ...current,
    mode: nextSettings.indexMode,
    embedding_model_configured: embeddingConfigured,
    total_projects: projects.length,
    total_chapters: sum((project) => project.total_chapters),
    indexed_count: sum((project) => project.indexed_count),
    pending_count: sum((project) => project.pending_count),
    in_progress_count: sum((project) => project.in_progress_count),
    failed_count: sum((project) => project.failed_count),
    projects,
  };
}

export function IndexSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: settings, isLoading: isSettingsLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });
  const { data: models, isLoading: isModelsLoading } = useQuery({
    queryKey: ["models"],
    queryFn: () => fetchModels(),
  });
  const { data: providers, isLoading: isProvidersLoading } = useQuery({
    queryKey: ["model-providers"],
    queryFn: fetchProviders,
  });
  const { data: projectsData, isLoading: isProjectsLoading } = useQuery({
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
    [overall.data?.projects],
  );
  const projectOptions = useMemo(
    () =>
      (projectsData?.items ?? []).map((project) => ({ value: project.id, label: project.title })),
    [projectsData?.items],
  );
  const projectIdsKey = projectIds.join("|");
  useEffect(() => {
    if (projectIds.length === 0) return;
    const subs = projectIds.map((pid) =>
      subscribeBackgroundEvents(pid, (event: BackgroundEvent) => {
        if (event.job_type !== "retrieval_chapter_index_batch") return;
        if (event.type === "background_job_cancelled") {
          void queryClient.invalidateQueries({
            queryKey: OVERALL_INDEX_STATUS_QUERY_KEY,
          });
          return;
        }
        if (event.type === "background_job_failed") {
          const message =
            typeof event.payload?.message === "string"
              ? event.payload.message
              : t("index.indexFailedUnknown");
          toast.error(t("index.indexFailed", { message }));
        }
      }),
    );
    return () => subs.forEach((s) => s.close());
    // projectIdsKey 变化时重新订阅。
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [projectIdsKey, queryClient, t]);

  const updateSettingsMutation = useMutation({
    mutationFn: updateSettings,
    onMutate: async (patch) => {
      // 乐观更新：立即将补丁合并进缓存，记录前值以便回滚。
      await Promise.all([
        queryClient.cancelQueries({ queryKey: ["settings"] }),
        queryClient.cancelQueries({ queryKey: OVERALL_INDEX_STATUS_QUERY_KEY }),
      ]);

      const previousSettings = queryClient.getQueryData<Settings>(["settings"]);
      const previousOverall = queryClient.getQueryData<OverallIndexStatus>(
        OVERALL_INDEX_STATUS_QUERY_KEY,
      );

      if (previousSettings) {
        const nextSettings = patchSettings(previousSettings, patch);
        queryClient.setQueryData<Settings>(["settings"], nextSettings);

        if (previousOverall && projectsData) {
          queryClient.setQueryData<OverallIndexStatus>(
            OVERALL_INDEX_STATUS_QUERY_KEY,
            patchOverallIndexStatus(
              previousOverall,
              nextSettings,
              projectsData.items,
              nextSettings.defaultEmbeddingModel !== "" &&
                embeddingModelIds.has(nextSettings.defaultEmbeddingModel),
            ),
          );
        }
      }

      return { previousSettings, previousOverall };
    },
    onError: (_error, _patch, context) => {
      if (context?.previousSettings) {
        queryClient.setQueryData(["settings"], context.previousSettings);
      }
      if (context?.previousOverall) {
        queryClient.setQueryData(OVERALL_INDEX_STATUS_QUERY_KEY, context.previousOverall);
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
    return (models?.filter((m) => m.taskType === "embedding") ?? []).map((model) => {
      const provider = providers?.find((entry) => entry.id === model.providerId);
      const providerIconPath = provider ? resolveProviderIconPath(provider) : null;

      return {
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
        providerIconPath,
      };
    });
  }, [models, providers]);

  const embeddingModelIds = useMemo(
    () =>
      new Set(
        (models?.filter((model) => model.taskType === "embedding") ?? []).map((model) => model.id),
      ),
    [models],
  );

  const [pendingEmbeddingModelId, setPendingEmbeddingModelId] = useState<string | null>(null);
  const [chunkSize, setChunkSize] = useState<string>(String(settings?.indexChunkSize ?? 800));
  const [chunkOverlap, setChunkOverlap] = useState<string>(
    String(settings?.indexChunkOverlap ?? 100),
  );

  const rerankModelOptions: ModelIdSelectOption[] = useMemo(() => {
    return (models?.filter((m) => m.taskType === "rerank") ?? []).map((model) => {
      const provider = providers?.find((entry) => entry.id === model.providerId);
      const providerIconPath = provider ? resolveProviderIconPath(provider) : null;

      return {
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
        providerIconPath,
      };
    });
  }, [models, providers]);

  const handleRerankModelChange = useCallback(
    (value: string) => {
      updateSettingsMutation.mutate({
        default_rerank_model: value,
        index_rerank_enabled: value !== "",
      });
    },
    [updateSettingsMutation],
  );

  // 当服务端分块参数变化时（如被其他端修改），同步本地输入。
  const [lastServerSize, setLastServerSize] = useState<number | undefined>(
    settings?.indexChunkSize,
  );
  const [lastServerOverlap, setLastServerOverlap] = useState<number | undefined>(
    settings?.indexChunkOverlap,
  );
  if (
    settings &&
    (settings.indexChunkSize !== lastServerSize || settings.indexChunkOverlap !== lastServerOverlap)
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
  }, [
    chunkSize,
    chunkOverlap,
    settings?.indexChunkSize,
    settings?.indexChunkOverlap,
    updateSettingsMutation,
  ]);

  const modeOptions = useMemo(
    () => [
      { value: "off", label: t("index.enableOff") },
      { value: "all", label: t("index.enableAll") },
      { value: "selected", label: t("index.enableSelected") },
    ],
    [t],
  );
  const autoStrategyOptions = useMemo(
    () => [
      { value: "immediate", label: t("index.autoImmediate") },
      { value: "agent_decided", label: t("index.autoAgentDecided") },
      { value: "off", label: t("index.autoOff") },
    ],
    [t],
  );

  const handleModeChange = useCallback(
    (mode: IndexMode) => {
      updateSettingsMutation.mutate({ index_mode: mode });
    },
    [updateSettingsMutation],
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
    [settings?.defaultEmbeddingModel, updateSettingsMutation],
  );

  const confirmEmbeddingModelChange = useCallback(() => {
    if (pendingEmbeddingModelId === null) return;
    updateSettingsMutation.mutate({ default_embedding_model: pendingEmbeddingModelId });
    setPendingEmbeddingModelId(null);
  }, [pendingEmbeddingModelId, updateSettingsMutation]);

  const handleAutoStrategyChange = useCallback(
    (strategy: IndexAutoStrategy) => {
      updateSettingsMutation.mutate({
        index_auto_strategy: strategy,
      });
    },
    [updateSettingsMutation],
  );

  const isContentLoading =
    isSettingsLoading ||
    !settings ||
    isModelsLoading ||
    isProvidersLoading ||
    !models ||
    isProjectsLoading ||
    !projectsData ||
    (Boolean(settings) && overall.isLoading && !overall.data);

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

  const projectGroups = toProjectIndexGroups(overall.data);
  const totalIndexUnits = projectGroups.reduce((sum, group) => sum + group.units.length, 0);
  const totalPendingUnits = projectGroups.reduce(
    (sum, group) => sum + group.units.reduce((unitSum, unit) => unitSum + unit.pending, 0),
    0,
  );

  return (
    <Box>
      <Flex
        direction="column"
        gap="5"
      >
        <IndexSettingsOverview
          embeddingConfigured={overall.data?.embedding_model_configured ?? false}
          enabledProjects={overall.data?.total_projects ?? 0}
          indexUnits={totalIndexUnits}
          indexed={overall.data?.indexed_count ?? 0}
          pending={totalPendingUnits}
          failed={overall.data?.failed_count ?? 0}
        />

        <IndexSettingsGlobalConfig
          settings={settings}
          embeddingModelOptions={embeddingModelOptions}
          rerankModelOptions={rerankModelOptions}
          projectOptions={projectOptions}
          modeOptions={modeOptions}
          autoStrategyOptions={autoStrategyOptions}
          chunkSize={chunkSize}
          chunkOverlap={chunkOverlap}
          onEmbeddingModelChange={handleEmbeddingModelChange}
          onRerankModelChange={handleRerankModelChange}
          onModeChange={handleModeChange}
          onAutoStrategyChange={handleAutoStrategyChange}
          onEnabledProjectsChange={(projectIds) => {
            updateSettingsMutation.mutate({ index_enabled_projects: projectIds });
          }}
          onChunkSizeChange={(value) => {
            setChunkSize(value);
            scheduleChunkSave();
          }}
          onChunkOverlapChange={(value) => {
            setChunkOverlap(value);
            scheduleChunkSave();
          }}
        />

        <ProjectIndexList groups={projectGroups} />
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
