import { useCallback } from "react";
import type React from "react";

import { toast } from "@/components";
import i18n from "@/i18n";
import type {
  AgentForkResponse,
  AgentSessionCreateResponse,
  TokenUsageState,
} from "@/lib/agent.types";

import { useAgentSession } from "../../hooks/use-agent-session";
import { AgentMessages } from "./agent-messages";
import { AgentSpecialPanels } from "./agent-special-panels";
import { getAgentSpecialPanels, type AgentSpecialPanel } from "./agent-special-panels-state";

interface AgentSidebarProps {
  projectId: string;
  scrollToBottomKey?: string | null;
  modelId: string;
  agentKey?: string;
  inputValue: string;
  onClearInput: () => void;
  onSetInputValue?: (value: string) => void;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
  onTokenUsage?: (sessionId: string, usage: TokenUsageState) => void;
  onTaskUsageSnapshot?: (payload: {
    sessionId: string;
    taskId: string;
    tokenInput: number;
    tokenOutput: number;
    tokenCache: number;
  }) => void;
  onTaskUsageDelta?: (payload: {
    sessionId: string;
    taskId: string;
    tokenInput: number;
    tokenOutput: number;
    tokenCache: number;
  }) => void;
  onTaskTitleUpdated?: (taskId: string, title: string, updatedAt?: string) => void;
  onForkCreated?: (response: AgentForkResponse) => void | Promise<void>;
  onSessionCreated?: (response: AgentSessionCreateResponse) => void;
  projectedSpecialPanels?: AgentSpecialPanel[];
  onAtBottomChange?: (isAtBottom: boolean) => void;
  scrollToBottomFnRef?: React.MutableRefObject<(() => void) | null>;
}

export function useAgentSidebar({
  projectId,
  scrollToBottomKey,
  modelId,
  agentKey,
  inputValue,
  onClearInput,
  onSetInputValue,
  onOpenMentionChapter,
  onTokenUsage,
  onTaskUsageSnapshot,
  onTaskUsageDelta,
  onTaskTitleUpdated,
  onForkCreated,
  onSessionCreated,
  projectedSpecialPanels = [],
  onAtBottomChange,
  scrollToBottomFnRef,
}: AgentSidebarProps) {
  const {
    messages: agentMessages,
    pendingMessage,
    status: agentStatus,
    isRunning: isAgentRunning,
    isCompacting: isAgentCompacting,
    isRollbacking: isAgentRollbacking,
    currentStage: agentCurrentStage,
    sessionId: agentSessionId,
    startSession: startAgentSession,
    sendMessage: sendAgentMessage,
    resetSession: resetAgentSession,
    loadSession: loadAgentSession,
    disconnectTransport: disconnectAgentTransport,
    reconnectTransport: reconnectAgentTransport,
    compactSession: compactAgentSession,
    cancelPendingMessage,
    rollbackToRevision: rollbackAgentRevision,
    forkFromRevision: forkAgentFromRevision,
    handleToolApproval: handleAgentToolApproval,
    submitQuestionAnswer: submitAgentQuestionAnswer,
    abortSession: abortAgentSession,
  } = useAgentSession({
    projectId,
    modelId,
    agentKey,
    maxIterations: 5,
    onTokenUsage,
    onTaskUsageSnapshot,
    onTaskUsageDelta,
    onTaskTitleUpdated,
    onSessionCreated,
  });

  const handleSend = useCallback(async () => {
    if (agentStatus === "waiting_answer" || agentStatus === "waiting_approval") {
      toast.error(
        agentStatus === "waiting_answer"
          ? i18n.t("writing.aiSidebar.cannotSendWaitingAnswer")
          : i18n.t("writing.aiSidebar.cannotSendWaitingApproval"),
      );
      return;
    }
    if (pendingMessage) {
      toast.error(i18n.t("writing.aiSidebar.cannotSendPendingMessage"));
      return;
    }
    if (!inputValue.trim()) return;
    if (!modelId) {
      toast.error(i18n.t("writing.aiSidebar.noModelSelected"));
      return;
    }

    const messageToSend = inputValue;
    onClearInput();

    if (agentSessionId) {
      await sendAgentMessage(messageToSend);
      return;
    }

    await startAgentSession(messageToSend);
  }, [
    inputValue,
    agentStatus,
    modelId,
    onClearInput,
    agentSessionId,
    sendAgentMessage,
    startAgentSession,
    pendingMessage,
  ]);

  const handleCancelPendingMessage = useCallback(async (): Promise<void> => {
    const restored = await cancelPendingMessage();
    if (restored && onSetInputValue) {
      onSetInputValue(restored);
    }
  }, [cancelPendingMessage, onSetInputValue]);

  const handleRollback = useCallback(
    async (messageId: string): Promise<string | null> => {
      const result = await rollbackAgentRevision(messageId);
      if (result && onSetInputValue) {
        onSetInputValue(result);
      }
      return result;
    },
    [rollbackAgentRevision, onSetInputValue],
  );

  const handleFork = useCallback(
    async (sourceRevisionId: string): Promise<void> => {
      const result = await forkAgentFromRevision(sourceRevisionId);
      if (result) await onForkCreated?.(result);
    },
    [forkAgentFromRevision, onForkCreated],
  );
  const specialPanels = [...getAgentSpecialPanels(agentMessages), ...projectedSpecialPanels];
  const hasProjectedApprovalPanels = projectedSpecialPanels.some(
    (panel) => panel.kind === "approval",
  );

  return {
    messages: agentMessages,
    pendingMessage,
    status: agentStatus,
    isRunning: isAgentRunning,
    isCompacting: isAgentCompacting,
    isRollbacking: isAgentRollbacking,
    currentStage: agentCurrentStage,
    sessionId: agentSessionId,
    onSend: handleSend,
    onAbort: abortAgentSession,
    onCancelPendingMessage: handleCancelPendingMessage,
    resetSession: resetAgentSession,
    loadSession: loadAgentSession,
    disconnectTransport: disconnectAgentTransport,
    reconnectTransport: reconnectAgentTransport,
    compactSession: compactAgentSession,
    rollbackToRevision: handleRollback,
    MessagesComponent: (
      <AgentMessages
        messages={agentMessages}
        isRunning={isAgentRunning}
        isRollbacking={isAgentRollbacking}
        status={agentStatus}
        currentStage={agentCurrentStage}
        scrollToBottomKey={scrollToBottomKey}
        onRollback={handleRollback}
        onFork={handleFork}
        onOpenMentionChapter={onOpenMentionChapter}
        onAtBottomChange={onAtBottomChange}
        scrollToBottomFnRef={scrollToBottomFnRef}
      />
    ),
    SpecialPanelsComponent: (
      <AgentSpecialPanels
        panels={specialPanels}
        embedded
        onApproveTool={
          agentStatus === "waiting_approval" || hasProjectedApprovalPanels
            ? handleAgentToolApproval
            : undefined
        }
        onSubmitQuestionAnswer={submitAgentQuestionAnswer}
      />
    ),
  };
}
