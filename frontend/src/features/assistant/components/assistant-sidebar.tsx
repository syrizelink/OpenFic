import {
  forwardRef,
  useState,
  useCallback,
  useRef,
  useEffect,
  useMemo,
  useImperativeHandle,
} from "react";
import NumberFlow from "@number-flow/react";

import { Box, Flex, IconButton, Spinner, Text, Tooltip } from "@radix-ui/themes";
import { ArrowBigDown, ArrowBigUp, ArrowDown, ArrowLeft, History, Layers2, ListChevronsDownUp, SquareArrowOutUpRight, SquarePen } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchActiveSubagents,
  fetchAgentSessionState,
  fetchTask,
  subscribeBackgroundEvents,
} from "@/lib/api-client";
import { useLlmModelOptions } from "@/lib/use-llm-model-options";
import { fetchSettings, updateSettings } from "@/features/settings/lib/settings-api";
import { fetchAgentDefinitions } from "@/features/settings/lib/agent-definitions-api";
import { CircularProgress, ConfirmDialog, toast, getModelValue } from "@/components";
import type {
  ActiveSubagentState,
  AgentForkResponse,
  AgentSessionCreateResponse,
  AgentMessage,
  TokenUsageState,
} from "@/lib/agent.types";
import type { TaskListItem } from "@/lib/task.types";
import { useSummaryPanel } from "@/features/writing/hooks/use-summaries";
import { useVolumeTree } from "@/features/writing/hooks/use-volumes";
import { useAppShell } from "@/features/app-shell";
import { appendMentionMarkup } from "@/features/assistant/lib/mention-text";
import "./assistant-sidebar.css";

import type { AssistantView } from "../lib/assistant.types";
import {
  createConversationStackState,
  getCurrentConversationDescriptor,
  getCurrentSubagentSnapshot,
  openSubagentConversation,
  returnToPrimaryConversation,
  syncParentConversationState,
  type AssistantConversationStackState,
} from "../lib/assistant-conversation-state";
import { buildAgentMessagesFromTaskMessages } from "../lib/task-message-agent-mapping";
import type { AssistantSidebarState } from "../lib/assistant-state.types";
import {
  joinSubagentStatusStream,
  subscribeSubagentStatusEvents,
} from "../lib/subagent-socket";
import { formatSubagentDisplayLabel } from "../lib/subagent-display";
import { createPendingApprovalMessage } from "../lib/subagent-session-approval";
import { loadAgentTaskBundle } from "../lib/agent-task-bundle";
import { useTasks, useUpdateTask } from "../hooks/use-tasks";
import { useSubagentSession } from "../hooks/use-subagent-session";
import { AgentInput, AgentMessages, useAgentSidebar } from "./agent";
import { AgentSpecialPanels } from "./agent/agent-special-panels";
import { getAgentSpecialPanels } from "./agent/agent-special-panels-state";
import { ActiveSubagentList } from "./agent/active-subagent-list";
import { RecentTasksCard } from "./tasks/recent-tasks-card";
import { AllTasksPage } from "./tasks/all-tasks-page";

interface AssistantSidebarProps {
  projectId: string;
  onStateChange?: (state: AssistantSidebarState) => void;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
  onClose?: () => void;
  isMobileOverlay?: boolean;
}

export interface AssistantSidebarHandle {
  appendToComposer: (markup: string) => void;
}

const ASSISTANT_MODEL_STORAGE_KEY = "openfic.agent.selectedModelId";
const ASSISTANT_AGENT_STORAGE_KEY = "openfic.agent.selectedAgentKey";
const DEFAULT_CONTEXT_LENGTH = 128000;

const CONTEXT_MID_FIELD_CHAPTER_COUNT = 10;
const CONTEXT_NEAR_FIELD_CHAPTER_COUNT = 9;
interface SessionTotalUsageState {
  sessionId: string;
  taskId: string | null;
  tokenInput: number;
  tokenOutput: number;
  tokenCache: number;
}

function upsertActiveSubagent(
  items: ActiveSubagentState[],
  nextItem: ActiveSubagentState
): ActiveSubagentState[] {
  const remaining = items.filter((item) => item.childRunId !== nextItem.childRunId);
  if (!nextItem.isActive) return remaining;
  return [...remaining, nextItem].sort((left, right) => left.agentKey.localeCompare(right.agentKey));
}

function needsContextCompletionWarning(status: string, isStale: boolean): boolean {
  if (status === "ready" && !isStale) return false;
  return status === "not_generated" || status === "failed" || status === "queued" || status === "running";
}

function createTokenUsageState(contextLength = DEFAULT_CONTEXT_LENGTH): TokenUsageState {
  return {
    tokenInput: 0,
    tokenOutput: 0,
    tokenCache: 0,
    contextInputTokens: 0,
    contextLength,
  };
}

function createSessionTotalUsageState(
  sessionId = "",
  taskId: string | null = null
): SessionTotalUsageState {
  return {
    sessionId,
    taskId,
    tokenInput: 0,
    tokenOutput: 0,
    tokenCache: 0,
  };
}

function getSubagentStatusLabel(
  status: ActiveSubagentState["status"] | "" | undefined,
  t: (key: string, options?: Record<string, unknown>) => string
): string {
  if (status === "queued") return t("writing.aiSidebar.subagentStatusQueued");
  if (status === "running") return t("writing.aiSidebar.subagentStatusRunning");
  if (status === "waiting_user") return t("writing.aiSidebar.subagentStatusWaitingUser");
  if (status === "completed") return t("writing.aiSidebar.subagentStatusCompleted");
  if (status === "error") return t("writing.aiSidebar.subagentStatusError");
  if (status === "cancelled") return t("writing.aiSidebar.subagentStatusCancelled");
  return t("writing.aiSidebar.subagentInactive");
}

function formatTokenCount(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return String(value);
}

function getAnimatedTokenDisplay(value: number): { value: number; suffix: string } {
  if (value >= 1000000) {
    return {
      value: Number((value / 1000000).toFixed(1)),
      suffix: "M",
    };
  }
  if (value >= 1000) {
    return {
      value: Number((value / 1000).toFixed(1)),
      suffix: "K",
    };
  }
  return { value, suffix: "" };
}

function AnimatedTokenCount({ value }: { value: number }) {
  const display = getAnimatedTokenDisplay(value);

  return (
    <NumberFlow
      value={display.value}
      suffix={display.suffix}
      locales="en-US"
      format={{
        minimumFractionDigits: display.suffix ? 1 : 0,
        maximumFractionDigits: display.suffix ? 1 : 0,
      }}
      className="ai-sidebar-token-number"
    />
  );
}

function buildTaskConversationUsage(
  task: {
    tokenInput: number;
    tokenOutput: number;
    tokenCache: number;
    contextInputTokens: number;
  },
  contextLength: number
): TokenUsageState {
  return {
    tokenInput: task.tokenInput,
    tokenOutput: task.tokenOutput,
    tokenCache: task.tokenCache,
    contextInputTokens: task.contextInputTokens,
    contextLength,
  };
}

export const AssistantSidebar = forwardRef<AssistantSidebarHandle, AssistantSidebarProps>(function AssistantSidebar({
  projectId,
  onStateChange,
  onOpenMentionChapter,
  onClose,
  isMobileOverlay = false,
}: AssistantSidebarProps, ref) {
  const { t } = useTranslation();
  const { openSettings } = useAppShell();
  const queryClient = useQueryClient();

  const [selectedModelId, setSelectedModelId] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    return window.localStorage.getItem(ASSISTANT_MODEL_STORAGE_KEY) ?? "";
  });
  const [selectedAgentKey, setSelectedAgentKey] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    return window.localStorage.getItem(ASSISTANT_AGENT_STORAGE_KEY) ?? "";
  });
  const [conversationState, setConversationState] = useState<AssistantConversationStackState>(
    () => createConversationStackState("")
  );
  const [activeSubagents, setActiveSubagents] = useState<ActiveSubagentState[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [view, setView] = useState<AssistantView>("tasks");
  const [isLoadingTask, setIsLoadingTask] = useState(false);
  const [currentTaskTitle, setCurrentTaskTitle] = useState<string>("");
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [summaryWarningOpen, setSummaryWarningOpen] = useState(false);
  const [sessionTotalUsage, setSessionTotalUsage] = useState<SessionTotalUsageState>(
    () => createSessionTotalUsageState()
  );
  const [conversationUsageBySession, setConversationUsageBySession] = useState<
    Record<string, TokenUsageState>
  >({});
  const pendingSendActionRef = useRef<(() => void) | null>(null);
  const [isMessagesAtBottom, setIsMessagesAtBottom] = useState(true);
  const scrollToBottomFnRef = useRef<(() => void) | null>(null);

  const { data: tasksData, refetch: refetchRecentTasks } = useTasks(projectId, { limit: 3 });
  const updateTaskMutation = useUpdateTask();
  const { data: chaptersData } = useVolumeTree(projectId);
  const { data: summaryPanelData } = useSummaryPanel(projectId);

  const {
    options: llmModelOptions,
    isLoading: isModelsLoading,
    error: modelsError,
  } = useLlmModelOptions();

  const { data: agentDefinitions = [] } = useQuery({
    queryKey: ["agent-definitions"],
    queryFn: fetchAgentDefinitions,
    staleTime: 5 * 60 * 1000,
  });

  const primaryAgents = useMemo(
    () => agentDefinitions.filter((d) => d.kind === "primary" && d.enabled),
    [agentDefinitions]
  );

  const effectiveAgentKey = useMemo(() => {
    if (selectedAgentKey) {
      const matched = primaryAgents.find((d) => d.key === selectedAgentKey);
      if (matched) return matched.key;
    }
    const fallback = primaryAgents.find((d) => d.key === "primary");
    if (fallback) return fallback.key;
    if (primaryAgents.length > 0) return primaryAgents[0].key;
    return "";
  }, [selectedAgentKey, primaryAgents]);

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    staleTime: 5 * 60 * 1000,
  });

  const {
    mutate: toggleToolApprovalBypass,
    isPending: isTogglingToolApprovalBypass,
  } = useMutation({
    mutationFn: async (enabled: boolean) => updateSettings({
      agent_bypass_tool_approval: enabled,
    }),
    onSuccess: (savedSettings) => {
      queryClient.setQueryData(["settings"], savedSettings);
    },
    onError: () => {
      toast.error("更新工具审批放行设置失败");
    },
  });

  const effectiveModelId = useMemo(() => {
    if (selectedModelId && llmModelOptions.some((model) => getModelValue(model) === selectedModelId)) {
      return selectedModelId;
    }
    const defaultModelId = settings?.defaultModel;
    if (defaultModelId && llmModelOptions.some((model) => getModelValue(model) === defaultModelId)) {
      return defaultModelId;
    }
    if (llmModelOptions.length > 0) return getModelValue(llmModelOptions[0]);
    return "";
  }, [selectedModelId, llmModelOptions, settings?.defaultModel]);

  const currentModel = useMemo(
    () => llmModelOptions.find((model) => getModelValue(model) === effectiveModelId),
    [effectiveModelId, llmModelOptions]
  );
  const isToolApprovalBypassEnabled = settings?.agentBypassToolApproval ?? false;
  const agentSidebarRef = useRef<ReturnType<typeof useAgentSidebar> | null>(null);

  useImperativeHandle(
    ref,
    () => ({
      appendToComposer(markup: string) {
        if (!markup.trim()) return;
        setView("tasks");
        setInputValue((current) => appendMentionMarkup(current, markup));
      },
    }),
    []
  );

  useEffect(() => {
    if (selectedModelId) {
      window.localStorage.setItem(ASSISTANT_MODEL_STORAGE_KEY, selectedModelId);
    }
  }, [selectedModelId]);

  useEffect(() => {
    if (selectedAgentKey) {
      window.localStorage.setItem(ASSISTANT_AGENT_STORAGE_KEY, selectedAgentKey);
    }
  }, [selectedAgentKey]);

  const handleAgentTaskTitleUpdated = useCallback(
    (taskId: string, title: string, updatedAt?: string) => {
      setCurrentTaskId(taskId);
      setCurrentTaskTitle(title);
      queryClient.setQueriesData({ queryKey: ["tasks", projectId], exact: false }, (current) => {
        if (!current || typeof current !== "object" || !("items" in current)) return current;
        const response = current as { items: TaskListItem[]; total: number };
        return {
          ...response,
          items: response.items.map((task) =>
            task.id === taskId
              ? { ...task, title, updatedAt: updatedAt ?? task.updatedAt }
              : task
          ),
        };
      });
      queryClient.setQueryData(["task", taskId], (current) => {
        if (!current || typeof current !== "object") return current;
        return { ...current, title, updatedAt: updatedAt ?? (current as { updatedAt?: string }).updatedAt };
      });
    },
    [projectId, queryClient]
  );

  const handleAgentForkCreated = useCallback(
    async (response: AgentForkResponse) => {
      try {
        const fullTask = await fetchTask(response.task_id);
        const forkTask: TaskListItem = {
          id: fullTask.id,
          projectId: fullTask.projectId,
          title: fullTask.title,
          tokenInput: fullTask.tokenInput,
          tokenOutput: fullTask.tokenOutput,
          tokenCache: fullTask.tokenCache,
          contextInputTokens: fullTask.contextInputTokens,
          isRunning: fullTask.isRunning,
          isFavorited: fullTask.isFavorited,
          createdAt: fullTask.createdAt,
          updatedAt: fullTask.updatedAt,
        };
        const agentMessages = buildAgentMessagesFromTaskMessages(
          fullTask.messages,
          forkTask,
          fullTask.createdAt
        );
        if (!fullTask.agentSessionId) {
          toast.error("分叉任务缺少Agent会话ID");
          return;
        }
        const sessionId = fullTask.agentSessionId;
        agentSidebarRef.current?.loadSession(sessionId, agentMessages, {
          reconnect: false,
          isRemoteRunning: false,
        });
        setView("tasks");
        setIsLoadingTask(false);
        setCurrentTaskId(fullTask.id);
        setCurrentTaskTitle(fullTask.title);
        setSessionTotalUsage({
          sessionId,
          taskId: fullTask.id,
          tokenInput: fullTask.tokenInput,
          tokenOutput: fullTask.tokenOutput,
          tokenCache: fullTask.tokenCache,
        });
        setConversationUsageBySession((current) => ({
          ...current,
          [sessionId]: buildTaskConversationUsage(
            fullTask,
            currentModel?.contextWindow ?? DEFAULT_CONTEXT_LENGTH
          ),
        }));
        queryClient.invalidateQueries({ queryKey: ["tasks", projectId], exact: false });
      } catch (error) {
        console.error("Failed to load fork task:", error);
        toast.error("分叉任务加载失败");
      }
    },
    [currentModel, projectId, queryClient]
  );

  const handleToggleToolApprovalBypass = useCallback(() => {
    if (isTogglingToolApprovalBypass) return;
    const nextEnabled = !isToolApprovalBypassEnabled;
    toggleToolApprovalBypass(nextEnabled);
  }, [isToolApprovalBypassEnabled, isTogglingToolApprovalBypass, toggleToolApprovalBypass]);

  const handleAgentSessionCreated = useCallback(
    (response: AgentSessionCreateResponse) => {
      setCurrentTaskId(response.task_id);
      setCurrentTaskTitle(response.task_title);
      setSessionTotalUsage(createSessionTotalUsageState(response.session_id, response.task_id));
      setConversationUsageBySession((current) => ({
        ...current,
        [response.session_id]: createTokenUsageState(
          currentModel?.contextWindow ?? DEFAULT_CONTEXT_LENGTH
        ),
      }));
    },
    [currentModel?.contextWindow]
  );

  const handleConversationTokenUsage = useCallback(
    (sessionId: string, usage: TokenUsageState) => {
      setConversationUsageBySession((current) => ({
        ...current,
        [sessionId]: usage,
      }));
    },
    []
  );

  const handleTaskUsageSnapshot = useCallback(
    (payload: {
      sessionId: string;
      taskId: string;
      tokenInput: number;
      tokenOutput: number;
      tokenCache: number;
    }) => {
      setSessionTotalUsage((current) => {
        if (current.sessionId && current.sessionId !== payload.sessionId) return current;
        return {
          sessionId: payload.sessionId,
          taskId: payload.taskId,
          tokenInput: payload.tokenInput,
          tokenOutput: payload.tokenOutput,
          tokenCache: payload.tokenCache,
        };
      });
    },
    []
  );

  const handleTaskUsageDelta = useCallback(
    (payload: {
      sessionId: string;
      taskId: string;
      tokenInput: number;
      tokenOutput: number;
      tokenCache: number;
    }) => {
      setSessionTotalUsage((current) => {
        if (current.sessionId && current.sessionId !== payload.sessionId) return current;
        return {
          sessionId: payload.sessionId,
          taskId: payload.taskId,
          tokenInput: current.tokenInput + payload.tokenInput,
          tokenOutput: current.tokenOutput + payload.tokenOutput,
          tokenCache: current.tokenCache + payload.tokenCache,
        };
      });
    },
    []
  );

  const currentConversation = useMemo(
    () => getCurrentConversationDescriptor(conversationState),
    [conversationState]
  );
  const currentSubagentSnapshot = useMemo(
    () => getCurrentSubagentSnapshot(conversationState),
    [conversationState]
  );
  const isViewingSubagent = currentConversation?.kind === "subagent";
  const projectedSubagentSpecialPanels = useMemo(() => {
    if (isViewingSubagent) return [];
    const approvalMessages = activeSubagents.reduce<AgentMessage[]>((result, subagent) => {
      const message = createPendingApprovalMessage(subagent.pendingApproval);
      if (message) result.push(message);
      return result;
    }, []);
    return getAgentSpecialPanels(approvalMessages);
  }, [activeSubagents, isViewingSubagent]);

  const agentSidebar = useAgentSidebar({
    projectId,
    scrollToBottomKey: currentTaskId,
    modelId: effectiveModelId,
    agentKey: effectiveAgentKey,
    inputValue,
    onClearInput: () => setInputValue(""),
    onSetInputValue: (value) => setInputValue(value),
    onOpenMentionChapter,
    onTokenUsage: handleConversationTokenUsage,
    onTaskUsageSnapshot: handleTaskUsageSnapshot,
    onTaskUsageDelta: handleTaskUsageDelta,
    onTaskTitleUpdated: handleAgentTaskTitleUpdated,
    onForkCreated: handleAgentForkCreated,
    onSessionCreated: handleAgentSessionCreated,
    projectedSpecialPanels: projectedSubagentSpecialPanels,
    onAtBottomChange: setIsMessagesAtBottom,
    scrollToBottomFnRef,
  });
  useEffect(() => {
    agentSidebarRef.current = agentSidebar;
  }, [agentSidebar]);
  const agentSidebarSessionId = agentSidebar.sessionId;
  const reconnectAgentTransport = agentSidebar.reconnectTransport;
  const parentConversationSessionId =
    agentSidebarSessionId
    || (currentConversation?.kind === "parent"
      ? currentConversation.sessionId
      : currentConversation?.parentSessionId)
    || "";
  const subagentSession = useSubagentSession(
    currentConversation?.kind === "subagent" ? currentConversation.childRunId : null,
    currentConversation?.kind === "subagent" ? currentConversation.childThreadId : null,
    handleConversationTokenUsage
  );

  const currentConversationSessionId = currentConversation?.kind === "subagent"
    ? currentConversation.childThreadId
    : agentSidebarSessionId
      || (currentConversation?.kind === "parent" ? currentConversation.sessionId : "")
      || "";
  const currentConversationUsage = useMemo<TokenUsageState>(() => {
    if (isViewingSubagent) {
      return conversationUsageBySession[currentConversationSessionId]
        ?? subagentSession.tokenUsage
        ?? createTokenUsageState(currentModel?.contextWindow ?? DEFAULT_CONTEXT_LENGTH);
    }
    return conversationUsageBySession[currentConversationSessionId]
      ?? createTokenUsageState(currentModel?.contextWindow ?? DEFAULT_CONTEXT_LENGTH);
  }, [
    conversationUsageBySession,
    currentConversationSessionId,
    currentModel?.contextWindow,
    isViewingSubagent,
    subagentSession.tokenUsage,
  ]);
  const sessionTotalDisplay = useMemo(() => ({
    tokenInput: sessionTotalUsage.tokenInput,
    tokenOutput: sessionTotalUsage.tokenOutput,
    tokenCache: sessionTotalUsage.tokenCache,
  }), [sessionTotalUsage.tokenCache, sessionTotalUsage.tokenInput, sessionTotalUsage.tokenOutput]);

  const contextUsagePercent = Math.min(
    100,
    Math.max(
      0,
      currentConversationUsage.contextLength > 0
        ? (currentConversationUsage.contextInputTokens / currentConversationUsage.contextLength) * 100
        : 0
    )
  );
  const contextUsageTooltip = `上下文占用 ${formatTokenCount(currentConversationUsage.contextInputTokens)} / ${formatTokenCount(currentConversationUsage.contextLength)} (${contextUsagePercent.toFixed(1)}%)`;

  useEffect(() => {
    if (!onStateChange) return;
    onStateChange({
      agentStatus: isViewingSubagent ? subagentSession.status : agentSidebar.status,
      isAgentRunning: isViewingSubagent ? subagentSession.isRunning : agentSidebar.isRunning,
      conversationDescriptor: currentConversation,
      activeSubagents,
    });
  }, [
    activeSubagents,
    isViewingSubagent,
    agentSidebar.isRunning,
    agentSidebar.status,
    currentConversation,
    onStateChange,
    subagentSession.isRunning,
    subagentSession.status,
  ]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setConversationState(createConversationStackState(""));
      setActiveSubagents([]);
      setSessionTotalUsage(createSessionTotalUsageState());
      setConversationUsageBySession({});
    });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (!agentSidebarSessionId) return undefined;
    let cancelled = false;
    const sessionId = agentSidebarSessionId;
    queueMicrotask(() => {
      if (cancelled) return;
      setConversationState((current) => {
        const synced = syncParentConversationState(current, sessionId);
        const parentEntry = synced.entries[0];
        if (!parentEntry || parentEntry.kind !== "parent") return synced;
        const nextTaskId = currentTaskId ?? parentEntry.taskId ?? null;
        const nextTaskTitle = currentTaskTitle || parentEntry.taskTitle || null;
        if (parentEntry.taskId === nextTaskId && parentEntry.taskTitle === nextTaskTitle) {
          return synced;
        }
        return {
          entries: [
            {
              ...parentEntry,
              taskId: nextTaskId,
              taskTitle: nextTaskTitle,
            },
            ...synced.entries.slice(1),
          ],
        };
      });
    });
    return () => {
      cancelled = true;
    };
  }, [agentSidebarSessionId, currentTaskId, currentTaskTitle]);

  useEffect(() => {
    if (!agentSidebarSessionId) return;
    void reconnectAgentTransport();
  }, [
    agentSidebarSessionId,
    reconnectAgentTransport,
  ]);

  useEffect(() => {
    if (!parentConversationSessionId) return undefined;

    const cleanup = subscribeSubagentStatusEvents(
      parentConversationSessionId,
      (event) => {
        setActiveSubagents((current) => upsertActiveSubagent(current, event));
        setConversationState((current) => {
          let changed = false;
          const nextEntries = current.entries.map((entry) => {
            if (entry.kind !== "subagent" || entry.childRunId !== event.childRunId) return entry;
            changed = true;
            return {
              ...entry,
              subagent: event,
            };
          });
          return changed ? { entries: nextEntries } : current;
        });
      },
      (error) => {
        console.warn("Subagent status stream disconnected", error);
      }
    );

    void joinSubagentStatusStream(parentConversationSessionId).catch((error) => {
      console.warn("Failed to join subagent status stream", error);
    });

    return () => {
      cleanup();
    };
  }, [parentConversationSessionId]);

  useEffect(() => {
    if (!projectId) return;
    const subscription = subscribeBackgroundEvents(
      projectId,
      (event) => {
        if (event.type === "task_title_updated" && event.task_id && event.title) {
          const taskId = event.task_id;
          const title = event.title;
          if (taskId === currentTaskId) setCurrentTaskTitle(title);
          queryClient.setQueriesData({ queryKey: ["tasks", projectId], exact: false }, (current) => {
            if (!current || typeof current !== "object" || !("items" in current)) return current;
            const response = current as { items: TaskListItem[]; total: number };
            return {
              ...response,
              items: response.items.map((task) =>
                task.id === taskId
                  ? { ...task, title, updatedAt: event.updated_at ?? task.updatedAt }
                  : task
              ),
            };
          });
          queryClient.setQueryData(["task", taskId], (current) => {
            if (!current || typeof current !== "object") return current;
            return { ...current, title, updatedAt: event.updated_at ?? (current as { updatedAt?: string }).updatedAt };
          });
          return;
        }

        if (event.type === "task_run_status_updated" && event.task_id) {
          const taskId = event.task_id;
          const isRunning = event.is_running === true;
          queryClient.setQueryData(["task", taskId], (current) => {
            if (!current || typeof current !== "object") return current;
            return {
              ...current,
              isRunning,
              updatedAt: event.updated_at ?? (current as { updatedAt?: string }).updatedAt,
            };
          });
          void queryClient.invalidateQueries({
            queryKey: ["tasks", projectId],
            exact: false,
          });
        }
      },
      () => {
        console.warn("Background event stream disconnected");
      }
    );
    return () => subscription.close();
  }, [currentTaskId, projectId, queryClient]);

  const loadTaskById = useCallback(
    async (
      taskId: string,
      options: {
        initialTask?: TaskListItem;
        showSuccessToast?: boolean;
      } = {}
    ): Promise<boolean> => {
      setView("tasks");
      setIsLoadingTask(true);
      setActiveSubagents([]);

      try {
        const bundle = await loadAgentTaskBundle(taskId, {
          fetchTask,
          fetchAgentSessionState,
          fetchActiveSubagents,
        });
        const fullTask = bundle.task;

        if (!fullTask.agentSessionId) {
          toast.error("Agent会话ID不存在，无法恢复任务");
          setIsLoadingTask(false);
          return false;
        }
        const sessionId = fullTask.agentSessionId;

        const taskSnapshot = options.initialTask ?? {
          id: fullTask.id,
          projectId: fullTask.projectId,
          title: fullTask.title,
          tokenInput: fullTask.tokenInput,
          tokenOutput: fullTask.tokenOutput,
          tokenCache: fullTask.tokenCache,
          contextInputTokens: fullTask.contextInputTokens,
          isRunning: fullTask.isRunning,
          isFavorited: fullTask.isFavorited,
          createdAt: fullTask.createdAt,
          updatedAt: fullTask.updatedAt,
        };

        const agentMessages = buildAgentMessagesFromTaskMessages(
          fullTask.messages,
          taskSnapshot,
          fullTask.createdAt
        );

        const isRemoteRunning = bundle.sessionState?.isRunning ?? false;

        agentSidebar.loadSession(sessionId, agentMessages, {
          reconnect: true,
          isRemoteRunning,
        });
        setActiveSubagents(bundle.activeSubagentRows);
        setCurrentTaskId(fullTask.id);
        setCurrentTaskTitle(fullTask.title);
        setConversationState((current) => {
          const synced = syncParentConversationState(current, sessionId);
          const parentEntry = synced.entries[0];
          if (!parentEntry || parentEntry.kind !== "parent") return synced;
          return {
            entries: [
              {
                ...parentEntry,
                taskId: fullTask.id,
                taskTitle: fullTask.title,
              },
              ...synced.entries.slice(1),
            ],
          };
        });
        setSessionTotalUsage({
          sessionId,
          taskId: fullTask.id,
          tokenInput: fullTask.tokenInput,
          tokenOutput: fullTask.tokenOutput,
          tokenCache: fullTask.tokenCache,
        });
        setConversationUsageBySession((current) => ({
          ...current,
          [sessionId]: buildTaskConversationUsage(
            fullTask,
            currentModel?.contextWindow ?? DEFAULT_CONTEXT_LENGTH
          ),
        }));

        if (options.showSuccessToast !== false) {
          toast.success("Agent任务已加载");
        }
        setIsLoadingTask(false);
        return true;
      } catch {
        setIsLoadingTask(false);
        toast.error(t("writing.aiSidebar.taskLoadFailed"));
        return false;
      }
    },
    [agentSidebar, currentModel?.contextWindow, t]
  );

  const loadTask = useCallback(
    async (task: TaskListItem) => {
      void loadTaskById(task.id, {
        initialTask: task,
      });
    },
    [loadTaskById]
  );

  const handleToggleFavorite = useCallback(
    (taskId: string, isFavorited: boolean) => {
      updateTaskMutation.mutate({
        taskId,
        data: { is_favorited: isFavorited },
      });
    },
    [updateTaskMutation]
  );

  const backToTaskList = useCallback(() => {
    setSessionTotalUsage(createSessionTotalUsageState());
    setConversationUsageBySession({});

    agentSidebar.resetSession();

    setConversationState(createConversationStackState(""));
    setActiveSubagents([]);
    setView("tasks");
    setIsLoadingTask(false);
    setCurrentTaskId(null);
    setCurrentTaskTitle("");
    void refetchRecentTasks();
  }, [agentSidebar, refetchRecentTasks]);

  const openAllTasks = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["tasks", projectId], exact: false });
    setView("allTasks");
  }, [projectId, queryClient]);

  const latestChapterOrder = useMemo(
    () =>
      Math.max(
        0,
        ...((chaptersData?.volumes ?? []).flatMap((volume) =>
          volume.chapters.map((chapter) => chapter.order)
        ))
      ),
    [chaptersData?.volumes]
  );

  const hasIncompleteContextSummaries = useMemo(() => {
    const maintenance = summaryPanelData?.maintenance;
    if (!maintenance || latestChapterOrder <= 0) return false;

    const midStartOrder = Math.max(1, latestChapterOrder - CONTEXT_NEAR_FIELD_CHAPTER_COUNT - CONTEXT_MID_FIELD_CHAPTER_COUNT);
    const midEndOrder = latestChapterOrder - CONTEXT_NEAR_FIELD_CHAPTER_COUNT - 1;
    const hasIncompleteMidSummaries = midEndOrder >= midStartOrder
      && maintenance.missingOrFailedChapterSummaries.some((item) => {
        if (!needsContextCompletionWarning(item.status, item.isStale)) return false;
        return item.chapterOrder >= midStartOrder && item.chapterOrder <= midEndOrder;
      });

    const farMaxEndOrder = latestChapterOrder - CONTEXT_NEAR_FIELD_CHAPTER_COUNT - CONTEXT_MID_FIELD_CHAPTER_COUNT - 1;
    const hasIncompleteFarSummaries = farMaxEndOrder >= 1
      && maintenance.missingOrFailedLongTermSummaries.some((item) => {
        if (!needsContextCompletionWarning(item.status, item.isStale)) return false;
        return item.endOrder <= farMaxEndOrder;
      });

    return hasIncompleteMidSummaries || hasIncompleteFarSummaries;
  }, [latestChapterOrder, summaryPanelData?.maintenance]);

  const performSend = useCallback(() => {
    const hasCurrentTask = Boolean(agentSidebar.sessionId);

    if (!hasCurrentTask && inputValue.trim()) {
      const title = inputValue.trim();
      setCurrentTaskTitle(title.length > 50 ? `${title.slice(0, 50)}...` : title);
    }

    agentSidebar.onSend();
  }, [inputValue, agentSidebar]);

  const handleSend = useCallback(() => {
    if (!inputValue.trim()) return;
    if (!hasIncompleteContextSummaries) {
      performSend();
      return;
    }

    pendingSendActionRef.current = performSend;
    setSummaryWarningOpen(true);
  }, [hasIncompleteContextSummaries, inputValue, performSend]);

  const handleConfirmSummaryWarning = useCallback(() => {
    setSummaryWarningOpen(false);
    const action = pendingSendActionRef.current;
    pendingSendActionRef.current = null;
    action?.();
  }, []);

  const handleSummaryWarningOpenChange = useCallback((open: boolean) => {
    setSummaryWarningOpen(open);
    if (!open) pendingSendActionRef.current = null;
  }, []);

  const handleAbort = useCallback(() => {
    agentSidebar.onAbort();
  }, [agentSidebar]);

  const canCompactAgentSession = Boolean(agentSidebar.sessionId)
    && !isViewingSubagent
    && !isLoadingTask
    && !agentSidebar.isRunning
    && !agentSidebar.isCompacting
    && (
      agentSidebar.status === "idle"
      || agentSidebar.status === "completed"
      || agentSidebar.status === "error"
    );
  const compactionTooltip = agentSidebar.isCompacting
    ? "正在压缩上下文"
    : isLoadingTask
      ? "正在加载会话"
    : isViewingSubagent
      ? "子会话不能手动压缩"
      : agentSidebar.isRunning
        ? "Agent运行中不能手动压缩"
        : agentSidebar.status === "waiting_answer" || agentSidebar.status === "waiting_approval"
          ? "请先处理当前会话"
          : agentSidebar.sessionId
            ? "压缩上下文"
            : "当前没有Agent会话";
  const handleCompactSession = useCallback(() => {
    if (!canCompactAgentSession) return;
    void agentSidebar.compactSession();
  }, [agentSidebar, canCompactAgentSession]);

  const handleModelChange = useCallback((nextModelId: string) => {
    setSelectedModelId(nextModelId);
    window.localStorage.setItem(ASSISTANT_MODEL_STORAGE_KEY, nextModelId);
  }, []);

  const handleAgentChange = useCallback((nextAgentKey: string) => {
    setSelectedAgentKey(nextAgentKey);
    window.localStorage.setItem(ASSISTANT_AGENT_STORAGE_KEY, nextAgentKey);
  }, []);

  const agentSelectorOptions = useMemo(
    () =>
      primaryAgents.map((d) => ({
        value: d.key,
        label: d.display_name || d.key,
      })),
    [primaryAgents]
  );

  const handleGoToSettings = useCallback(() => {
    openSettings({ category: "models", modelTab: "llm" });
  }, [openSettings]);

  const handleOpenSubagent = useCallback((subagent: ActiveSubagentState) => {
    if (!parentConversationSessionId) return;
    setConversationState((current) =>
      openSubagentConversation(current, parentConversationSessionId, subagent)
    );
  }, [parentConversationSessionId]);

  const handleReturnToPrimary = useCallback(async () => {
    const parentEntry = conversationState.entries[0];
    if (
      !agentSidebar.sessionId
      && parentEntry?.kind === "parent"
      && typeof parentEntry.taskId === "string"
      && parentEntry.taskId
    ) {
      const restored = await loadTaskById(parentEntry.taskId, {
        showSuccessToast: false,
      });
      if (!restored) return;
    }
    setConversationState((current) => returnToPrimaryConversation(current));
  }, [agentSidebar.sessionId, conversationState.entries, loadTaskById]);

  const recentTasks = tasksData?.items ?? [];
  const hasRecentTasks = recentTasks.length > 0;

  const hasActiveTask = Boolean(parentConversationSessionId);

  const shouldShowMobileToolbar = isMobileOverlay && view !== "allTasks" && !hasActiveTask;

  const isSendingMessage = agentSidebar.isRunning;
  const shouldShowSubagentConversation = isViewingSubagent;
  const shouldShowParentSubagentStrip = view !== "allTasks"
    && hasActiveTask
    && !isLoadingTask
    && !isViewingSubagent
    && activeSubagents.length > 0;
  const subagentSpecialPanels = useMemo(
    () => getAgentSpecialPanels(subagentSession.messages),
    [subagentSession.messages]
  );
  const subagentHeaderLabel = formatSubagentDisplayLabel(
    subagentSession.session?.agentKey ?? currentSubagentSnapshot?.agentKey,
    subagentSession.session?.agentNumber ?? currentSubagentSnapshot?.agentNumber
  );
  const subagentStatusValue = subagentSession.session?.status ?? currentSubagentSnapshot?.status ?? "";
  const subagentStatusLabel = getSubagentStatusLabel(subagentStatusValue, t);
  const subagentReadOnlyMessage = (
    <span className="ai-sidebar-readonly-message">
      {!subagentStatusValue ? (
        <span>{t("writing.aiSidebar.subagentInactive")} · </span>
      ) : null}
      <span>{t("writing.aiSidebar.subagentReadOnly")}</span>
      <button
        type="button"
        className="ai-sidebar-readonly-return-link"
        onClick={() => {
          void handleReturnToPrimary();
        }}
        aria-label={t("writing.aiSidebar.returnToPrimary")}
      >
        <span className="ai-sidebar-readonly-return-label">
          {t("writing.aiSidebar.returnToPrimary")}
        </span>
        <SquareArrowOutUpRight
          size={12}
          strokeWidth={2}
          className="ai-sidebar-readonly-return-icon"
          aria-hidden="true"
        />
      </button>
    </span>
  );
  const headerBackLabel = isViewingSubagent ? t("writing.aiSidebar.returnToPrimary") : t("common.back");
  const handleHeaderBack = isViewingSubagent ? handleReturnToPrimary : backToTaskList;

  return (
    <Flex
      direction="column"
      height="100%"
      className="ai-sidebar-shell"
    >
      {shouldShowMobileToolbar && (
        <Flex align="center" gap="2" className="ai-sidebar-mobile-toolbar">
          <IconButton
            variant="ghost"
            size="2"
            onClick={onClose}
            aria-label={t("common.close")}
          >
            <ArrowLeft size={18} />
          </IconButton>
          <Text size="2" weight="medium">
            {t("assistant.mobileTitle")}
          </Text>
        </Flex>
      )}

      {view !== "allTasks" && hasActiveTask && (
        <Box className="ai-sidebar-header">
          <Flex align="center" justify="between" gap="2" className="ai-sidebar-task-header-row">
            <Flex align="center" gap="2" className="ai-sidebar-task-title-wrap">
              <IconButton
                variant="ghost"
                size="1"
                onClick={handleHeaderBack}
                aria-label={headerBackLabel}
              >
                <ArrowLeft size={16} />
              </IconButton>
              {isViewingSubagent ? (
                <Flex align="center" gap="2" className="ai-sidebar-task-title-stack">
                  <Text
                    size="2"
                    weight="medium"
                    title={subagentHeaderLabel || t("assistant.subagentFallbackTitle")}
                    className="ai-sidebar-task-title"
                  >
                    {subagentHeaderLabel || t("assistant.subagentFallbackTitle")}
                  </Text>
                  <Text size="1" color="gray" className="ai-sidebar-task-subtitle">
                    {subagentStatusLabel}
                  </Text>
                </Flex>
              ) : (
                <Text
                  size="2"
                  weight="medium"
                  title={currentTaskTitle || t("assistant.taskFallbackTitle")}
                  className="ai-sidebar-task-title"
                >
                  {currentTaskTitle || t("assistant.taskFallbackTitle")}
                </Text>
              )}
            </Flex>

            <Flex align="center" gap="1" className="ai-sidebar-task-actions">
              <Tooltip content={compactionTooltip}>
                <IconButton
                  variant="ghost"
                  color="gray"
                  size="1"
                  onClick={handleCompactSession}
                  disabled={!canCompactAgentSession}
                  aria-label={t("assistant.compactContext")}
                  aria-busy={agentSidebar.isCompacting || undefined}
                >
                  {agentSidebar.isCompacting ? <Spinner size="1" /> : <ListChevronsDownUp size={16} />}
                </IconButton>
              </Tooltip>
              <IconButton
                variant="ghost"
                color="gray"
                size="1"
                onClick={openAllTasks}
                aria-label={t("assistant.history")}
              >
                <History size={16} />
              </IconButton>
              <IconButton
                variant="ghost"
                color="gray"
                size="1"
                onClick={backToTaskList}
                aria-label={t("assistant.newTask")}
              >
                <SquarePen size={16} />
              </IconButton>
            </Flex>
          </Flex>
          <Flex align="center" justify="between" gap="3" className="ai-sidebar-token-row">
            <Flex align="center" gap="2" className="ai-sidebar-token-metrics">
              <Text size="1" weight="medium" color="gray">{t("assistant.tokens")}</Text>
              <Tooltip content={t("assistant.totalOutputTokens", { count: sessionTotalDisplay.tokenOutput })}>
                <Flex align="center" gap="1" className="ai-sidebar-token-metric">
                  <ArrowBigUp size={13} />
                  <Text as="span" size="1">
                    <AnimatedTokenCount value={sessionTotalDisplay.tokenOutput} />
                  </Text>
                </Flex>
              </Tooltip>
              <Tooltip content={t("assistant.totalInputTokens", { count: sessionTotalDisplay.tokenInput })}>
                <Flex align="center" gap="1" className="ai-sidebar-token-metric">
                  <ArrowBigDown size={13} />
                  <Text as="span" size="1">
                    <AnimatedTokenCount value={sessionTotalDisplay.tokenInput} />
                  </Text>
                </Flex>
              </Tooltip>
              <Tooltip content={t("assistant.cachedTokens", { count: sessionTotalDisplay.tokenCache })}>
                <Flex align="center" gap="1" className="ai-sidebar-token-metric">
                  <Layers2 size={13} />
                  <Text as="span" size="1">
                    <AnimatedTokenCount value={sessionTotalDisplay.tokenCache} />
                  </Text>
                </Flex>
              </Tooltip>
            </Flex>
            <Flex align="center" className="ai-sidebar-context-wrap">
              <Tooltip content={contextUsageTooltip}>
                <Box asChild className="ai-sidebar-context-indicator-hitbox">
                  <CircularProgress
                    value={currentConversationUsage.contextInputTokens}
                    max={currentConversationUsage.contextLength}
                    size={16}
                    strokeWidth={1.75}
                    ariaLabel={t("assistant.contextUsage")}
                  />
                </Box>
              </Tooltip>
            </Flex>
          </Flex>
        </Box>
      )}

      {shouldShowParentSubagentStrip ? (
        <Box className="ai-sidebar-subagent-strip-wrap">
          <ActiveSubagentList
            items={activeSubagents}
            title={t("writing.aiSidebar.activeSubagents")}
            onOpen={handleOpenSubagent}
          />
        </Box>
      ) : null}

      {view === "allTasks" ? (
        <AllTasksPage
          projectId={projectId}
          onBack={() => {
            setView("tasks");
            void refetchRecentTasks();
          }}
          onTaskClick={loadTask}
        />
      ) : (
        <>
          <Box className="ai-sidebar-messages ai-sidebar-messages--frame">
            {isLoadingTask ? (
              <Flex direction="column" align="center" justify="center" className="ai-sidebar-loading-state">
                <Spinner size="2" />
                <Text size="2" color="gray">{t("assistant.loadingTask")}</Text>
              </Flex>
            ) : shouldShowSubagentConversation ? (
              <AgentMessages
                messages={subagentSession.messages}
                isRunning={subagentSession.isRunning}
                isRollbacking={false}
                status={subagentSession.status}
                currentStage={subagentSession.currentStage}
                scrollToBottomKey={
                  currentConversation?.kind === "subagent"
                    ? currentConversation.childRunId
                    : undefined
                }
                onRollback={async () => null}
                onAtBottomChange={setIsMessagesAtBottom}
                scrollToBottomFnRef={scrollToBottomFnRef}
              />
            ) : !hasActiveTask ? (
              <RecentTasksCard
                tasks={recentTasks}
                hasRecentTasks={hasRecentTasks}
                onTaskClick={loadTask}
                onToggleFavorite={handleToggleFavorite}
                onViewAll={openAllTasks}
              />
            ) : (
              agentSidebar.MessagesComponent
            )}
          </Box>

          <div
            className="ai-sidebar-scroll-to-bottom"
            data-visible={!isLoadingTask && hasActiveTask && !isMessagesAtBottom}
          >
            <IconButton
              size="2"
              variant="soft"
              color="gray"
              onClick={() => scrollToBottomFnRef.current?.()}
              aria-label={t("assistant.scrollToBottom")}
            >
              <ArrowDown size={16} />
            </IconButton>
          </div>

          <AgentInput
            specialPanels={isViewingSubagent
              ? (
                <AgentSpecialPanels
                  panels={subagentSpecialPanels}
                  embedded
                  onApproveTool={subagentSession.handleToolApproval}
                  readOnly
                />
              )
              : agentSidebar.SpecialPanelsComponent}
            value={inputValue}
            projectId={projectId}
            modelId={effectiveModelId}
            models={llmModelOptions}
            isSending={isSendingMessage}
            disabled={isViewingSubagent || isLoadingTask}
            pendingMessage={isViewingSubagent ? null : agentSidebar.pendingMessage}
            isModelsLoading={isModelsLoading}
            modelsError={!!modelsError}
            onChange={setInputValue}
            onSend={isViewingSubagent ? () => undefined : handleSend}
            onAbort={isViewingSubagent ? () => undefined : handleAbort}
            onCancelPendingMessage={isViewingSubagent ? undefined : agentSidebar.onCancelPendingMessage}
            onOpenMentionChapter={onOpenMentionChapter}
            onModelChange={handleModelChange}
            agentKey={effectiveAgentKey}
            agentOptions={agentSelectorOptions}
            onAgentChange={handleAgentChange}
            onGoToSettings={handleGoToSettings}
            agentStatus={isViewingSubagent ? subagentSession.status : agentSidebar.status}
            toolApprovalBypassEnabled={isToolApprovalBypassEnabled}
            toolApprovalBypassDisabled={!settings || isTogglingToolApprovalBypass}
            onToggleToolApprovalBypass={handleToggleToolApprovalBypass}
            forceSpecialPanels={!isViewingSubagent && projectedSubagentSpecialPanels.length > 0}
            readOnly={isViewingSubagent}
            readOnlyMessage={subagentReadOnlyMessage}
          />
          <ConfirmDialog
            open={summaryWarningOpen}
            onOpenChange={handleSummaryWarningOpenChange}
            onConfirm={handleConfirmSummaryWarning}
            title={t("assistant.summaryWarningTitle")}
            description={t("assistant.summaryWarningDescription")}
            confirmText={t("assistant.summaryWarningConfirm")}
            cancelText={t("common.cancel")}
            confirmColor="blue"
          />
        </>
      )}
    </Flex>
  );
});
