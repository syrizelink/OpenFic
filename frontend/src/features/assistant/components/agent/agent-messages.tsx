/**
 * Agent Messages
 *
 * Agent 消息列表组件
 */

import { Box, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { Check, Copy, GitFork, RotateCcw } from "lucide-react";
import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog, toast } from "@/components";
import type { AgentMessage as AgentMessageType } from "@/lib/agent.types";

import { AgentMessageRenderer } from "./agent-message-renderer";
import {
  hasPendingLoadedSessionBottomRestore,
  resolveFollowBottomStateOnScroll,
  shouldAutoScrollOnFrameChange,
  shouldFollowBottom,
  shouldResetFollowBottomForLoad,
  shouldResetFollowBottomForRun,
  shouldScheduleLoadedSessionBottomRestoreImmediately,
  shouldTrackStreamingFollowBottom,
  type ScrollViewportMetrics,
} from "./agent-messages-scroll";
import { AgentStatusMessage } from "./agent-status-message";
import {
  buildAgentMessageBlocks,
  getAgentRoundToolbarTargets,
  getVisibleAgentMessageBlocks,
  type AgentRoundToolbarTarget,
} from "./display/agent-message-blocks";
import { buildAgentDisplayItems } from "./display/agent-message-display-items";
import { normalizeDisplayMessages } from "./display/display-message-normalization";

import "./agent-message-blocks.css";

import type {
  AgentBlockDisplayMessage,
  BlockDisplayMessage,
} from "./display/display-message-types";
import { ExplorationMessage } from "./message-blocks/blocks/exploration/exploration-message";

const COPY_FEEDBACK_MS = 1200;

function getTimestampParts(timestamp: number, timeZone?: string): Record<string, string> {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    hourCycle: "h23",
  });
  return formatter
    .formatToParts(new Date(timestamp))
    .reduce<Record<string, string>>((result, part) => {
      if (part.type !== "literal") result[part.type] = part.value;
      return result;
    }, {});
}

function formatAgentToolbarTimestamp(timestamp?: number, now = Date.now()): string {
  if (typeof timestamp !== "number" || !Number.isFinite(timestamp)) return "";
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const value = getTimestampParts(timestamp, timeZone);
  const current = getTimestampParts(now, timeZone);
  const hourMinute = `${value.hour}:${value.minute}`;
  if (value.year === current.year && value.month === current.month && value.day === current.day) {
    return hourMinute;
  }
  if (value.year === current.year) {
    return `${value.month}-${value.day} ${hourMinute}`;
  }
  return `${value.year}-${value.month}-${value.day} ${hourMinute}`;
}

interface AgentMessagesProps {
  messages: AgentMessageType[];
  isRunning: boolean;
  isRollbacking: boolean;
  status: "idle" | "running" | "waiting_answer" | "waiting_approval" | "completed" | "error";
  currentStage: string;
  scrollToBottomKey?: string | null;
  onRollback: (messageId: string) => Promise<string | null>;
  onFork?: (sourceRevisionId: string) => Promise<void>;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
  onAtBottomChange?: (isAtBottom: boolean) => void;
  scrollToBottomFnRef?: React.MutableRefObject<(() => void) | null>;
}

function isRollbackableUserMessage(message: AgentMessageType): boolean {
  return (
    (message.type === "user_request" || (message.type === "text" && message.role === "user")) &&
    Boolean(message.revisionId)
  );
}

function isAgentBlockDisplayMessage(
  message: BlockDisplayMessage,
): message is AgentBlockDisplayMessage {
  return (
    message.type !== "user_request" && message.type !== "node_start" && message.type !== "node_end"
  );
}

function areBlockMessageListsEqual(previous: BlockDisplayMessage[], next: BlockDisplayMessage[]) {
  if (previous === next) return true;
  if (previous.length !== next.length) return false;
  for (let index = 0; index < previous.length; index += 1) {
    if (previous[index] !== next[index]) return false;
  }
  return true;
}

interface AgentBlockContentProps {
  messages: BlockDisplayMessage[];
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
}

const AgentBlockContent = memo(
  function AgentBlockContent({ messages, onOpenMentionChapter }: AgentBlockContentProps) {
    const agentMessages = useMemo(() => messages.filter(isAgentBlockDisplayMessage), [messages]);
    const displayItems = useMemo(() => buildAgentDisplayItems(agentMessages), [agentMessages]);

    return (
      <Flex
        direction="column"
        gap="2"
        className="agent-message-block-content"
      >
        {displayItems.map((item) =>
          item.type === "exploration" ? (
            <ExplorationMessage
              key={item.id}
              messages={item.messages}
              summary={item.summary}
            />
          ) : (
            <AgentMessageRenderer
              key={item.id}
              message={item.message}
              onOpenMentionChapter={onOpenMentionChapter}
            />
          ),
        )}
      </Flex>
    );
  },
  (prev, next) =>
    areBlockMessageListsEqual(prev.messages, next.messages) &&
    prev.onOpenMentionChapter === next.onOpenMentionChapter,
);

export function AgentMessages({
  messages,
  isRunning,
  isRollbacking,
  status,
  currentStage,
  scrollToBottomKey,
  onRollback,
  onFork,
  onOpenMentionChapter,
  onAtBottomChange,
  scrollToBottomFnRef,
}: AgentMessagesProps) {
  const { t } = useTranslation();
  const contentRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLElement | null>(null);
  const shouldFollowBottomRef = useRef(true);
  const isRestoringLoadedSessionBottomRef = useRef(false);
  const pendingLoadedSessionRestoreKeyRef = useRef<string | null | undefined>(null);
  const restoreAttemptRef = useRef(0);
  const resizeFrameRef = useRef<{ scrollHeight: number; clientHeight: number } | null>(null);
  const viewportMetricsRef = useRef<ScrollViewportMetrics | null>(null);
  const previousIsRunningRef = useRef(isRunning);
  const lastLoadScrollKeyRef = useRef<string | null | undefined>(null);
  const copyFeedbackTimerRef = useRef<number | null>(null);
  const restoreScrollRafRef = useRef<number | null>(null);
  const streamingScrollRafRef = useRef<number | null>(null);
  const isAtBottomRef = useRef(true);
  const [copiedActionId, setCopiedActionId] = useState<string | null>(null);
  const [pendingRollbackMessage, setPendingRollbackMessage] = useState<AgentMessageType | null>(
    null,
  );
  const [pendingForkTarget, setPendingForkTarget] = useState<AgentRoundToolbarTarget | null>(null);
  const [collapsedNodeIds, setCollapsedNodeIds] = useState<Set<string>>(() => new Set());
  const latestMessage = messages.at(-1);
  const streamFollowSignal = [
    messages.length,
    latestMessage?.id ?? "",
    latestMessage?.type ?? "",
    latestMessage?.status ?? "",
    latestMessage?.content?.length ?? 0,
    latestMessage?.toolArgsText?.length ?? 0,
    latestMessage?.isStreaming ? 1 : 0,
  ].join(":");

  const getScrollContainer = useCallback(
    () => scrollContainerRef.current ?? bottomRef.current?.closest(".ai-sidebar-messages"),
    [],
  );

  const scrollContainerToBottom = useCallback((container: HTMLElement) => {
    container.scrollTop = container.scrollHeight;
  }, []);

  const scheduleStreamingScrollToBottom = useCallback(() => {
    const container = getScrollContainer();
    if (!(container instanceof HTMLElement)) return;
    if (!shouldFollowBottomRef.current) return;
    if (streamingScrollRafRef.current !== null) return;
    streamingScrollRafRef.current = window.requestAnimationFrame(() => {
      streamingScrollRafRef.current = null;
      const activeContainer = getScrollContainer();
      if (!(activeContainer instanceof HTMLElement)) return;
      if (!shouldFollowBottomRef.current) return;
      scrollContainerToBottom(activeContainer);
    });
  }, [getScrollContainer, scrollContainerToBottom]);

  const scheduleLoadedSessionBottomRestore = useCallback(() => {
    const hasPendingRestore = hasPendingLoadedSessionBottomRestore(
      pendingLoadedSessionRestoreKeyRef.current,
      scrollToBottomKey,
    );
    if (!hasPendingRestore) return;
    const container = getScrollContainer();
    if (!(container instanceof HTMLElement)) return;
    if (restoreScrollRafRef.current !== null) return;
    const restoreBottom = () => {
      restoreScrollRafRef.current = null;
      const activeContainer = getScrollContainer();
      if (!(activeContainer instanceof HTMLElement)) return;
      restoreAttemptRef.current += 1;
      scrollContainerToBottom(activeContainer);
      const isAtBottom = shouldFollowBottom({
        scrollHeight: activeContainer.scrollHeight,
        scrollTop: activeContainer.scrollTop,
        clientHeight: activeContainer.clientHeight,
      });
      if (isAtBottom) {
        isRestoringLoadedSessionBottomRef.current = false;
        pendingLoadedSessionRestoreKeyRef.current = null;
        return;
      }
      restoreScrollRafRef.current = window.requestAnimationFrame(restoreBottom);
    };
    restoreScrollRafRef.current = window.requestAnimationFrame(restoreBottom);
  }, [getScrollContainer, scrollContainerToBottom, scrollToBottomKey]);

  useEffect(() => {
    const sentinel = bottomRef.current;
    const container = sentinel?.closest(".ai-sidebar-messages");
    if (!(container instanceof HTMLElement)) return;
    scrollContainerRef.current = container;

    const handleScroll = () => {
      const nextViewport = {
        scrollHeight: container.scrollHeight,
        scrollTop: container.scrollTop,
        clientHeight: container.clientHeight,
      };
      const atBottom = shouldFollowBottom(nextViewport);
      if (isAtBottomRef.current !== atBottom) {
        isAtBottomRef.current = atBottom;
        onAtBottomChange?.(atBottom);
      }
      if (!shouldTrackStreamingFollowBottom(isRunning)) {
        return;
      }
      shouldFollowBottomRef.current = resolveFollowBottomStateOnScroll({
        previous: viewportMetricsRef.current,
        next: nextViewport,
        wasFollowingBottom: shouldFollowBottomRef.current,
      });
      viewportMetricsRef.current = nextViewport;
    };

    const syncFrameMetrics = () => {
      const nextFrame = {
        scrollHeight: container.scrollHeight,
        clientHeight: container.clientHeight,
      };
      const previousFrame = resizeFrameRef.current;
      resizeFrameRef.current = nextFrame;
      if (isRestoringLoadedSessionBottomRef.current) {
        scheduleLoadedSessionBottomRestore();
        return;
      }
      const atBottom = shouldFollowBottom({
        scrollHeight: container.scrollHeight,
        scrollTop: container.scrollTop,
        clientHeight: container.clientHeight,
      });
      if (isAtBottomRef.current !== atBottom) {
        isAtBottomRef.current = atBottom;
        onAtBottomChange?.(atBottom);
      }
      if (!shouldTrackStreamingFollowBottom(isRunning)) {
        return;
      }
      if (shouldAutoScrollOnFrameChange(previousFrame, nextFrame, shouldFollowBottomRef.current)) {
        scheduleStreamingScrollToBottom();
      }
    };

    handleScroll();
    syncFrameMetrics();

    const resizeObserver = new ResizeObserver(() => {
      syncFrameMetrics();
    });
    resizeObserver.observe(container);
    if (contentRef.current) {
      resizeObserver.observe(contentRef.current);
    }

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      if (restoreScrollRafRef.current !== null) {
        window.cancelAnimationFrame(restoreScrollRafRef.current);
        restoreScrollRafRef.current = null;
      }
      scrollContainerRef.current = null;
      resizeObserver.disconnect();
      container.removeEventListener("scroll", handleScroll);
    };
  }, [
    isRunning,
    onAtBottomChange,
    scheduleLoadedSessionBottomRestore,
    scheduleStreamingScrollToBottom,
  ]);

  useEffect(() => {
    const previousIsRunning = previousIsRunningRef.current;
    previousIsRunningRef.current = isRunning;
    if (shouldResetFollowBottomForRun(previousIsRunning, isRunning)) {
      shouldFollowBottomRef.current = true;
      scheduleStreamingScrollToBottom();
    }
    if (!shouldTrackStreamingFollowBottom(isRunning)) return;
    scheduleStreamingScrollToBottom();
  }, [currentStage, isRunning, scheduleStreamingScrollToBottom, streamFollowSignal]);

  useLayoutEffect(() => {
    const previousKey = lastLoadScrollKeyRef.current;
    lastLoadScrollKeyRef.current = scrollToBottomKey;
    const shouldRestore = shouldResetFollowBottomForLoad(previousKey, scrollToBottomKey);
    if (shouldRestore) {
      pendingLoadedSessionRestoreKeyRef.current = scrollToBottomKey;
      restoreAttemptRef.current = 0;
    } else if (!scrollToBottomKey) {
      pendingLoadedSessionRestoreKeyRef.current = null;
    }
    const hasPendingRestore = hasPendingLoadedSessionBottomRestore(
      pendingLoadedSessionRestoreKeyRef.current,
      scrollToBottomKey,
    );
    if (!hasPendingRestore) return;
    isRestoringLoadedSessionBottomRef.current = true;
    const shouldScheduleImmediately = shouldScheduleLoadedSessionBottomRestoreImmediately(
      hasPendingRestore,
      scrollContainerRef.current instanceof HTMLElement,
    );
    if (shouldScheduleImmediately) {
      scheduleLoadedSessionBottomRestore();
    }
  }, [isRunning, messages.length, scheduleLoadedSessionBottomRestore, scrollToBottomKey]);

  useEffect(() => {
    onAtBottomChange?.(isAtBottomRef.current);
  }, [onAtBottomChange]);

  useEffect(() => {
    if (!scrollToBottomFnRef) return;
    scrollToBottomFnRef.current = () => {
      const container = getScrollContainer();
      if (!(container instanceof HTMLElement)) return;
      shouldFollowBottomRef.current = true;
      scrollContainerToBottom(container);
      if (!isAtBottomRef.current) {
        isAtBottomRef.current = true;
        onAtBottomChange?.(true);
      }
    };
    return () => {
      scrollToBottomFnRef.current = null;
    };
  }, [scrollToBottomFnRef, getScrollContainer, scrollContainerToBottom, onAtBottomChange]);

  useEffect(
    () => () => {
      if (copyFeedbackTimerRef.current !== null) {
        window.clearTimeout(copyFeedbackTimerRef.current);
      }
      if (restoreScrollRafRef.current !== null) {
        window.cancelAnimationFrame(restoreScrollRafRef.current);
      }
      if (streamingScrollRafRef.current !== null) {
        window.cancelAnimationFrame(streamingScrollRafRef.current);
      }
      isRestoringLoadedSessionBottomRef.current = false;
      restoreAttemptRef.current = 0;
    },
    [],
  );

  const displayMessages = useMemo(() => normalizeDisplayMessages(messages), [messages]);
  const closeOpenNodeAt = useMemo(() => {
    if (isRunning) return undefined;
    return displayMessages.reduce<number | undefined>(
      (latest, message) =>
        typeof latest === "number" ? Math.max(latest, message.timestamp) : message.timestamp,
      undefined,
    );
  }, [displayMessages, isRunning]);
  const messageBlocks = useMemo(
    () => buildAgentMessageBlocks(displayMessages, { closeOpenNodeAt }),
    [closeOpenNodeAt, displayMessages],
  );
  const visibleMessageBlocks = useMemo(
    () => getVisibleAgentMessageBlocks(messageBlocks, collapsedNodeIds),
    [collapsedNodeIds, messageBlocks],
  );
  const toolbarTargets = useMemo(
    () => getAgentRoundToolbarTargets(messageBlocks, visibleMessageBlocks, { isRunning, status }),
    [isRunning, messageBlocks, status, visibleMessageBlocks],
  );
  const toolbarTargetByAnchorId = useMemo(
    () => new Map(toolbarTargets.map((target) => [target.anchorBlockId, target])),
    [toolbarTargets],
  );

  const toggleNodeCollapsed = useCallback((nodeId: string) => {
    setCollapsedNodeIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const copyText = useCallback(
    async (content: string, emptyMessage: string, actionId: string) => {
      const text = content.trim();
      if (!text) {
        toast.error(emptyMessage);
        return;
      }
      try {
        await navigator.clipboard.writeText(text);
        setCopiedActionId(actionId);
        if (copyFeedbackTimerRef.current !== null) {
          window.clearTimeout(copyFeedbackTimerRef.current);
        }
        copyFeedbackTimerRef.current = window.setTimeout(() => {
          setCopiedActionId(null);
          copyFeedbackTimerRef.current = null;
        }, COPY_FEEDBACK_MS);
        toast.success(t("common.copied"));
      } catch {
        toast.error(t("assistant.copyFailed"));
      }
    },
    [t],
  );

  const confirmRollback = useCallback(async () => {
    const messageId = pendingRollbackMessage?.id;
    setPendingRollbackMessage(null);
    if (!messageId) return;
    await onRollback(messageId);
  }, [onRollback, pendingRollbackMessage]);

  const confirmFork = useCallback(async () => {
    const sourceRevisionId = pendingForkTarget?.sourceRevisionId;
    setPendingForkTarget(null);
    if (!sourceRevisionId || !onFork) return;
    await onFork(sourceRevisionId);
  }, [onFork, pendingForkTarget]);

  const renderAgentRoundToolbar = (target: AgentRoundToolbarTarget) => {
    const actionId = `copy:${target.id}`;
    const isCopied = copiedActionId === actionId;
    const canFork = Boolean(target.sourceRevisionId && onFork && !isRollbacking && !isRunning);
    const timestampText = formatAgentToolbarTimestamp(target.timestamp);
    return (
      <Flex
        key={target.id}
        className="agent-message-round-toolbar agent-message-block-toolbar"
        data-align="left"
        align="center"
        gap="1"
      >
        <Tooltip content={isCopied ? t("common.copied") : t("assistant.copyLatestReply")}>
          <IconButton
            size="1"
            variant="ghost"
            color={isCopied ? "green" : "gray"}
            aria-label={
              isCopied ? t("assistant.latestReplyCopied") : t("assistant.copyLatestReply")
            }
            className="agent-message-block-toolbar-button"
            data-copied={isCopied ? "true" : undefined}
            disabled={!target.copyContent}
            onClick={() =>
              copyText(target.copyContent, t("assistant.noAssistantReplyToCopy"), actionId)
            }
          >
            {isCopied ? <Check size={13} /> : <Copy size={13} />}
          </IconButton>
        </Tooltip>
        {canFork && (
          <Tooltip content={t("assistant.forkTask")}>
            <IconButton
              size="1"
              variant="ghost"
              color="gray"
              aria-label={t("assistant.forkTask")}
              className="agent-message-block-toolbar-button"
              onClick={() => setPendingForkTarget(target)}
            >
              <GitFork size={13} />
            </IconButton>
          </Tooltip>
        )}
        {timestampText ? (
          <Text
            size="1"
            className="agent-message-block-toolbar-timestamp"
          >
            {timestampText}
          </Text>
        ) : null}
      </Flex>
    );
  };

  return (
    <Box
      className="agent-messages-root"
      data-rollbacking={isRollbacking ? "true" : undefined}
    >
      <Box
        ref={contentRef}
        className="agent-message-scroll-content"
      >
        {visibleMessageBlocks.map((block) => {
          const toolbarTarget = toolbarTargetByAnchorId.get(block.id);
          if (block.type === "node") {
            const message = block.messages[0];
            if (!message || message.type !== "node_start") return null;
            const nodeId = block.nodeId ?? message.id;
            const isCollapsed = collapsedNodeIds.has(nodeId);
            return (
              <Box
                key={block.id}
                className="agent-message-block-stack"
                data-block-type="node"
              >
                <Box
                  className="agent-message-block"
                  data-block-type="node"
                >
                  <AgentMessageRenderer
                    message={message}
                    nodeStartedAt={block.nodeStartedAt}
                    nodeEndedAt={block.nodeEndedAt}
                    nodeElapsedBaseMs={block.nodeElapsedBaseMs}
                    isNodeCollapsed={isCollapsed}
                    onToggleNode={() => toggleNodeCollapsed(nodeId)}
                    onOpenMentionChapter={onOpenMentionChapter}
                  />
                </Box>
                {toolbarTarget ? renderAgentRoundToolbar(toolbarTarget) : null}
              </Box>
            );
          }

          if (block.type === "user") {
            const message = block.messages[0];
            if (!message || message.type !== "user_request") return null;
            const canShowRollback =
              isRollbackableUserMessage(message) && !isRollbacking && !isRunning;
            const copyActionId = `copy:${block.id}`;
            const isCopied = copiedActionId === copyActionId;
            const timestampText = formatAgentToolbarTimestamp(message.timestamp);
            return (
              <Box
                key={block.id}
                className="agent-message-block"
                data-block-type="user"
              >
                <AgentMessageRenderer
                  message={message}
                  onOpenMentionChapter={onOpenMentionChapter}
                />
                <Flex
                  className="agent-message-block-toolbar"
                  data-align="right"
                  align="center"
                  gap="1"
                >
                  {timestampText ? (
                    <Text
                      size="1"
                      className="agent-message-block-toolbar-timestamp"
                    >
                      {timestampText}
                    </Text>
                  ) : null}
                  <Tooltip content={isCopied ? t("common.copied") : t("common.copy")}>
                    <IconButton
                      size="1"
                      variant="ghost"
                      color={isCopied ? "green" : "gray"}
                      aria-label={
                        isCopied ? t("assistant.userMessageCopied") : t("assistant.copyUserMessage")
                      }
                      className="agent-message-block-toolbar-button"
                      data-copied={isCopied ? "true" : undefined}
                      onClick={() =>
                        copyText(
                          message.content ?? "",
                          t("assistant.noUserMessageToCopy"),
                          copyActionId,
                        )
                      }
                    >
                      {isCopied ? <Check size={13} /> : <Copy size={13} />}
                    </IconButton>
                  </Tooltip>
                  {canShowRollback && (
                    <Tooltip content={t("assistant.rollbackToHere")}>
                      <IconButton
                        size="1"
                        variant="ghost"
                        color="gray"
                        aria-label={t("assistant.rollbackToHere")}
                        className="agent-message-block-toolbar-button"
                        onClick={() => setPendingRollbackMessage(message)}
                      >
                        <RotateCcw size={13} />
                      </IconButton>
                    </Tooltip>
                  )}
                </Flex>
              </Box>
            );
          }

          return (
            <Box
              key={block.id}
              className="agent-message-block-stack"
              data-block-type="agent"
            >
              <Box
                className="agent-message-block"
                data-block-type="agent"
              >
                <AgentBlockContent
                  messages={block.messages}
                  onOpenMentionChapter={onOpenMentionChapter}
                />
              </Box>
              {toolbarTarget ? renderAgentRoundToolbar(toolbarTarget) : null}
            </Box>
          );
        })}

        {(status === "running" || status === "waiting_answer" || status === "waiting_approval") &&
          currentStage && <AgentStatusMessage content={currentStage} />}
        <Box
          ref={bottomRef}
          className="agent-message-bottom-anchor"
        />
      </Box>
      <ConfirmDialog
        open={Boolean(pendingRollbackMessage)}
        onOpenChange={(open) => {
          if (!open && !isRollbacking) setPendingRollbackMessage(null);
        }}
        onConfirm={confirmRollback}
        title={t("assistant.rollbackDialogTitle")}
        description={t("assistant.rollbackDialogDescription")}
        confirmText={t("assistant.rollbackDialogConfirm")}
        loading={isRollbacking}
      />
      <ConfirmDialog
        open={Boolean(pendingForkTarget)}
        onOpenChange={(open) => {
          if (!open) setPendingForkTarget(null);
        }}
        onConfirm={confirmFork}
        title={t("assistant.forkDialogTitle")}
        description={t("assistant.forkDialogDescription")}
        confirmText={t("assistant.forkDialogConfirm")}
        confirmColor="blue"
      />
    </Box>
  );
}
