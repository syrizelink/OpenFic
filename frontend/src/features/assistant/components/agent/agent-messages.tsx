/**
 * Agent Messages
 *
 * Agent 消息列表组件
 */

import { Box, Button, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { Check, Copy, GitFork, RotateCcw } from "lucide-react";
import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ComponentPropsWithRef,
} from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";

import { ConfirmDialog, Spinner, toast } from "@/components";
import type {
  AgentChangeSummary,
  AgentMessage as AgentMessageType,
  AgentSessionChanges,
} from "@/lib/agent.types";

import { AgentChangeSummaryCard } from "./agent-changes";
import { AgentMessageNavigation } from "./agent-message-navigation";
import {
  buildAgentMessageNavigationItems,
  getActiveMessageNavigationIndex,
} from "./agent-message-navigation-utils";
import { AgentMessageRenderer } from "./agent-message-renderer";
import {
  getStreamingFollowSignal,
  getPrependedBlockCount,
  resolveFollowBottomStateOnScroll,
  shouldAutoScrollOnFrameChange,
  shouldFollowBottom,
  shouldResetFollowBottomForRun,
  shouldTrackStreamingFollowBottom,
  type ScrollViewportMetrics,
} from "./agent-messages-scroll";
import { getAgentRunningStatus } from "./agent-running-status";
import { AgentStatusMessage } from "./agent-status-message";
import {
  buildAgentRoundChangeSummaries,
  buildAgentMessageBlocks,
  getAgentRoundToolbarTargets,
  getVisibleAgentMessageBlocks,
  type AgentRoundToolbarTarget,
} from "./display/agent-message-blocks";
import type { AgentMessageBlock } from "./display/agent-message-blocks";
import { buildAgentDisplayItems } from "./display/agent-message-display-items";

import "./agent-message-blocks.css";

import { normalizeDisplayMessages } from "./display/display-message-normalization";
import type {
  AgentBlockDisplayMessage,
  BlockDisplayMessage,
} from "./display/display-message-types";
import { ExplorationMessage } from "./message-blocks/blocks/exploration/exploration-message";

const COPY_FEEDBACK_MS = 1200;
const MAX_BOTTOM_RESTORE_ATTEMPTS = 120;
const INITIAL_FIRST_ITEM_INDEX = 1_000_000_000;

function estimateAgentBlockHeight(block: AgentMessageBlock, hasChangeSummary = false): number {
  const changeSummaryHeight = hasChangeSummary ? 150 : 0;
  if (block.type === "node") return 120 + changeSummaryHeight;
  if (block.type === "user") return 100;
  return 120 + block.messages.length * 90 + changeSummaryHeight;
}

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
  isAttachmentProcessing?: boolean;
  currentStage: string;
  scrollToBottomKey?: string | null;
  onRollback: (messageId: string) => Promise<string | null>;
  onFork?: (sourceRevisionId: string) => Promise<void>;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
  onAbortRetry?: () => void;
  changes?: AgentSessionChanges | null;
  onOpenChanges?: (summary: AgentChangeSummary, revisionId?: string) => void;
  onAtBottomChange?: (isAtBottom: boolean) => void;
  onLoadingChange?: (isLoading: boolean) => void;
  scrollToBottomFnRef?: React.MutableRefObject<(() => void) | null>;
  messagesHasMore?: boolean;
  isLoadingEarlier?: boolean;
  hasEarlierError?: boolean;
  historyGeneration?: number;
  onLoadEarlier?: (retry?: boolean) => Promise<void>;
}

function isRollbackableUserMessage(message: AgentMessageType): boolean {
  return (
    (message.type === "user_request" || (message.type === "text" && message.role === "user")) &&
    Boolean(message.revisionId)
  );
}

function getCurrentRoundStartedAt(messages: AgentMessageType[]): number | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (
      (message.type === "user_request" || (message.type === "text" && message.role === "user")) &&
      Number.isFinite(message.timestamp)
    ) {
      return message.timestamp;
    }
  }
  return undefined;
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
  onAbortRetry?: () => void;
}

const AgentBlockContent = memo(
  function AgentBlockContent({
    messages,
    onOpenMentionChapter,
    onAbortRetry,
  }: AgentBlockContentProps) {
    const agentMessages = useMemo(() => messages.filter(isAgentBlockDisplayMessage), [messages]);
    const [displayState, setDisplayState] = useState(() => ({
      messages: agentMessages,
      items: buildAgentDisplayItems(agentMessages),
    }));
    let displayItems = displayState.items;
    if (displayState.messages !== agentMessages) {
      displayItems = buildAgentDisplayItems(agentMessages, displayState.items);
      setDisplayState({ messages: agentMessages, items: displayItems });
    }

    return (
      <Flex
        direction="column"
        gap="2"
        className="agent-message-block-content"
      >
        {displayItems.map((item) => (
          <Box
            key={item.id}
            data-scroll-message-ids={JSON.stringify(
              item.type === "exploration"
                ? item.messages.map((message) => message.id)
                : [item.message.id],
            )}
          >
            {item.type === "exploration" ? (
              <ExplorationMessage
                messages={item.messages}
                summary={item.summary}
              />
            ) : (
              <AgentMessageRenderer
                message={item.message}
                onOpenMentionChapter={onOpenMentionChapter}
                onAbortRetry={onAbortRetry}
              />
            )}
          </Box>
        ))}
      </Flex>
    );
  },
  (prev, next) =>
    areBlockMessageListsEqual(prev.messages, next.messages) &&
    prev.onOpenMentionChapter === next.onOpenMentionChapter &&
    prev.onAbortRetry === next.onAbortRetry,
);

interface AgentMessagesFooterContext {
  statusMessage: string;
  showStatus: boolean;
  roundStartedAt?: number;
  bottomRef: React.RefObject<HTMLDivElement | null>;
  scrollParent: HTMLElement | null;
  onLoadingChange?: (isLoading: boolean) => void;
  showHistoryLoading: boolean;
  hasEarlierError: boolean;
  isRollbacking: boolean;
  onLoadEarlier: (retry?: boolean) => void;
  prependOffsetRef: React.MutableRefObject<number>;
  onHistoryHeaderGrow: (height: number) => void;
}

export function AgentMessagesLoading({
  scrollParent,
  onLoadingChange,
}: {
  scrollParent: HTMLElement | null;
  onLoadingChange?: (isLoading: boolean) => void;
}) {
  const { t } = useTranslation();
  useLayoutEffect(() => {
    onLoadingChange?.(true);
    return () => onLoadingChange?.(false);
  }, [onLoadingChange]);
  const host = scrollParent?.parentElement;
  if (!scrollParent || !host) return null;
  const bounds = scrollParent.getBoundingClientRect();
  const hostBounds = host.getBoundingClientRect();

  return createPortal(
    <Flex
      className="ai-sidebar-loading-state"
      align="center"
      justify="center"
      direction="column"
      gap="3"
      style={{ height: bounds.bottom - hostBounds.top }}
      role="status"
    >
      <Spinner size={18} />
      <Text
        size="2"
        color="gray"
      >
        {t("assistant.loadingTask")}
      </Text>
    </Flex>,
    host,
  );
}

function AgentMessagesList({
  context,
  ...props
}: ComponentPropsWithRef<"div"> & { context?: AgentMessagesFooterContext }) {
  const prependOffsetRef = context?.prependOffsetRef;
  const marginTop = props.style?.marginTop;
  useLayoutEffect(() => {
    if (prependOffsetRef) prependOffsetRef.current = typeof marginTop === "number" ? marginTop : 0;
  }, [prependOffsetRef, marginTop]);
  return (
    <>
      <div {...props} />
      {props.style?.visibility === "hidden" ? (
        <AgentMessagesLoading
          scrollParent={context?.scrollParent ?? null}
          onLoadingChange={context?.onLoadingChange}
        />
      ) : null}
    </>
  );
}

const AgentMessagesFooter = memo(function AgentMessagesFooter({
  context,
}: {
  context: AgentMessagesFooterContext;
}) {
  return (
    <>
      {context.showStatus ? (
        <AgentStatusMessage
          content={context.statusMessage}
          startedAt={context.roundStartedAt}
        />
      ) : null}
      <Box
        ref={context.bottomRef}
        className="agent-message-bottom-anchor"
      />
    </>
  );
});

function AgentMessagesHeader({ context }: { context: AgentMessagesFooterContext }) {
  const { t } = useTranslation();
  const { hasEarlierError, onHistoryHeaderGrow, scrollParent, showHistoryLoading } = context;
  const headerRef = useRef<HTMLDivElement | null>(null);
  const previousHeightRef = useRef(0);
  useLayoutEffect(() => {
    const height = headerRef.current?.getBoundingClientRect().height ?? 0;
    if (height > previousHeightRef.current) onHistoryHeaderGrow(height - previousHeightRef.current);
    if (height === 0 && previousHeightRef.current > 0 && scrollParent) {
      scrollParent.scrollTop = Math.max(0, scrollParent.scrollTop - previousHeightRef.current);
    }
    previousHeightRef.current = height;
  }, [hasEarlierError, onHistoryHeaderGrow, scrollParent, showHistoryLoading]);
  if (!context.showHistoryLoading && !context.hasEarlierError) return null;
  return (
    <Flex
      ref={headerRef}
      className="agent-message-history-status"
      align="center"
      justify="center"
      gap="2"
      role="status"
      aria-live="polite"
    >
      {context.showHistoryLoading ? (
        <>
          <Spinner size={12} />
          <Text
            size="1"
            color="gray"
          >
            {t("assistant.loadingEarlierMessages")}
          </Text>
        </>
      ) : (
        <>
          <Text
            size="1"
            color="gray"
          >
            {t("assistant.loadEarlierMessagesFailed")}
          </Text>
          <Button
            size="1"
            variant="ghost"
            onClick={() => context.onLoadEarlier(true)}
            disabled={context.isRollbacking}
          >
            {t("assistant.retryEarlierMessages")}
          </Button>
        </>
      )}
    </Flex>
  );
}

export function AgentMessages({
  messages,
  isRunning,
  isRollbacking,
  status,
  isAttachmentProcessing = false,
  currentStage,
  scrollToBottomKey,
  onRollback,
  onFork,
  onOpenMentionChapter,
  onAbortRetry,
  changes,
  onOpenChanges,
  onAtBottomChange,
  onLoadingChange,
  scrollToBottomFnRef,
  messagesHasMore = false,
  isLoadingEarlier = false,
  hasEarlierError = false,
  historyGeneration = 0,
  onLoadEarlier,
}: AgentMessagesProps) {
  const { t } = useTranslation();
  const contentRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const virtuosoRef = useRef<VirtuosoHandle | null>(null);
  const scrollContainerRef = useRef<HTMLElement | null>(null);
  const shouldFollowBottomRef = useRef(true);
  const isRestoringLoadedSessionBottomRef = useRef(false);
  const pendingLoadedSessionRestoreKeyRef = useRef<string | null | undefined>(null);
  const resizeFrameRef = useRef<{ scrollHeight: number; clientHeight: number } | null>(null);
  const viewportMetricsRef = useRef<ScrollViewportMetrics | null>(null);
  const previousIsRunningRef = useRef(isRunning);
  const lastLoadScrollKeyRef = useRef<string | null | undefined>(null);
  const copyFeedbackTimerRef = useRef<number | null>(null);
  const restoreScrollRafRef = useRef<number | null>(null);
  const streamingScrollRafRef = useRef<number | null>(null);
  const isAtBottomRef = useRef(true);
  const historyAnchorRef = useRef<{
    id: string;
    top: number;
    fallbacks: { id: string; top: number }[];
    messages: AgentMessageType[];
    blocks: AgentMessageBlock[];
    generation: number;
  } | null>(null);
  const visibleBlocksRef = useRef<AgentMessageBlock[]>([]);
  const prependOffsetRef = useRef(0);
  const historyRestoreRafRef = useRef<number | null>(null);
  const historyResizeObserverRef = useRef<ResizeObserver | null>(null);
  const historyLoadRafRef = useRef<number | null>(null);
  const isRestoringHistoryRef = useRef(false);
  const [isRestoringHistory, setIsRestoringHistory] = useState(false);
  const historyTopArmedRef = useRef(false);
  const handleHistoryHeaderGrow = useCallback((height: number) => {
    const anchor = historyAnchorRef.current;
    if (!anchor) return;
    anchor.top += height;
    for (const fallback of anchor.fallbacks) fallback.top += height;
  }, []);
  const cancelHistoryRestore = useCallback(() => {
    historyAnchorRef.current = null;
    isRestoringHistoryRef.current = false;
    setIsRestoringHistory(false);
    historyResizeObserverRef.current?.disconnect();
    historyResizeObserverRef.current = null;
    if (historyRestoreRafRef.current !== null)
      window.cancelAnimationFrame(historyRestoreRafRef.current);
    historyRestoreRafRef.current = null;
  }, []);
  const captureHistoryAnchor = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container || isRestoringHistoryRef.current) return;
    const top = container.getBoundingClientRect().top;
    const anchors = contentRef.current?.querySelectorAll<HTMLElement>("[data-scroll-message-ids]");
    const visibleAnchors = Array.from(anchors ?? []).filter((element) => {
      const rect = element.getBoundingClientRect();
      return (
        !element.closest('[aria-hidden="true"], [inert]') &&
        rect.height > 0 &&
        rect.bottom > top + 12
      );
    });
    const visibleAnchorSet = new Set(visibleAnchors);
    const candidates = visibleAnchors
      .filter(
        (element) =>
          !Array.from(element.querySelectorAll<HTMLElement>("[data-scroll-message-ids]")).some(
            (child) =>
              visibleAnchorSet.has(child) &&
              child.getBoundingClientRect().top < top + container.clientHeight,
          ),
      )
      .flatMap((element) => {
        const ids = JSON.parse(element.dataset.scrollMessageIds ?? "[]") as string[];
        return ids[0] ? [{ id: ids[0], top: element.getBoundingClientRect().top - top }] : [];
      });
    const anchor = candidates[0];
    if (!anchor || anchor.top >= container.clientHeight) return;
    historyAnchorRef.current = {
      ...anchor,
      fallbacks: candidates.slice(1),
      messages,
      blocks: visibleBlocksRef.current,
      generation: historyGeneration,
    };
  }, [historyGeneration, messages]);
  const handleLoadEarlier = useCallback(
    (retry = false) => {
      if (
        !onLoadEarlier ||
        isRollbacking ||
        isLoadingEarlier ||
        !messagesHasMore ||
        (hasEarlierError && !retry) ||
        isRestoringLoadedSessionBottomRef.current ||
        isRestoringHistoryRef.current ||
        historyLoadRafRef.current !== null
      )
        return;
      historyTopArmedRef.current = false;
      shouldFollowBottomRef.current = false;
      if (streamingScrollRafRef.current !== null) {
        window.cancelAnimationFrame(streamingScrollRafRef.current);
        streamingScrollRafRef.current = null;
      }
      // Virtuoso updates its visible range after the scroll event.
      historyLoadRafRef.current = window.requestAnimationFrame(() => {
        historyLoadRafRef.current = null;
        captureHistoryAnchor();
        void onLoadEarlier(retry);
      });
    },
    [
      captureHistoryAnchor,
      hasEarlierError,
      isLoadingEarlier,
      isRollbacking,
      messagesHasMore,
      onLoadEarlier,
    ],
  );
  const [copiedActionId, setCopiedActionId] = useState<string | null>(null);
  const [pendingRollbackMessage, setPendingRollbackMessage] = useState<AgentMessageType | null>(
    null,
  );
  const [pendingForkTarget, setPendingForkTarget] = useState<AgentRoundToolbarTarget | null>(null);
  const [collapsedNodeIds, setCollapsedNodeIds] = useState<Set<string>>(() => new Set());
  const [activeNavigationIndex, setActiveNavigationIndex] = useState(0);
  const streamFollowSignal = getStreamingFollowSignal(messages);
  const runningStatus = useMemo(() => getAgentRunningStatus(messages), [messages]);
  const roundStartedAt = useMemo(() => getCurrentRoundStartedAt(messages), [messages]);
  const statusMessage = isAttachmentProcessing
    ? t("assistant.runningStatus.attachmentProcessing")
    : status === "running"
      ? t(`assistant.runningStatus.${runningStatus ?? "considering"}`)
      : currentStage;

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
    if (isRestoringHistoryRef.current) return;
    if (streamingScrollRafRef.current !== null) return;
    streamingScrollRafRef.current = window.requestAnimationFrame(() => {
      streamingScrollRafRef.current = null;
      const activeContainer = getScrollContainer();
      if (!(activeContainer instanceof HTMLElement)) return;
      if (!shouldFollowBottomRef.current) return;
      if (isRestoringHistoryRef.current) return;
      scrollContainerToBottom(activeContainer);
    });
  }, [getScrollContainer, scrollContainerToBottom]);

  const scheduleLoadedSessionBottomRestore = useCallback(() => {
    if (!isRestoringLoadedSessionBottomRef.current) return;
    const key = pendingLoadedSessionRestoreKeyRef.current;
    if (!key) return;
    const container = getScrollContainer();
    if (!(container instanceof HTMLElement)) return;
    if (restoreScrollRafRef.current !== null) return;
    restoreScrollRafRef.current = window.requestAnimationFrame(() => {
      restoreScrollRafRef.current = null;
      if (pendingLoadedSessionRestoreKeyRef.current !== key) return;
      const activeContainer = getScrollContainer();
      if (!(activeContainer instanceof HTMLElement)) return;
      scrollContainerToBottom(activeContainer);
      isRestoringLoadedSessionBottomRef.current = false;
      pendingLoadedSessionRestoreKeyRef.current = null;
      shouldFollowBottomRef.current = true;
      isAtBottomRef.current = true;
      onAtBottomChange?.(true);
    });
  }, [getScrollContainer, onAtBottomChange, scrollContainerToBottom]);

  useEffect(() => {
    const container =
      scrollContainerRef.current ?? contentRef.current?.closest(".ai-sidebar-messages");
    if (!(container instanceof HTMLElement)) return;

    const handleScroll = () => {
      if (isRestoringLoadedSessionBottomRef.current) return;
      if (isRestoringHistoryRef.current) return;
      if (isLoadingEarlier && historyLoadRafRef.current === null) {
        historyLoadRafRef.current = window.requestAnimationFrame(() => {
          historyLoadRafRef.current = null;
          captureHistoryAnchor();
        });
      }
      if (container.scrollTop > 200) historyTopArmedRef.current = true;
      if (container.scrollTop <= 200 && historyTopArmedRef.current) handleLoadEarlier();
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
        isAutoScrollPending: streamingScrollRafRef.current !== null,
      });
      viewportMetricsRef.current = nextViewport;
    };

    const handleHistoryIntent = () => {
      if (isRestoringLoadedSessionBottomRef.current) return;
      if (isRestoringHistoryRef.current) {
        cancelHistoryRestore();
        return;
      }
      historyTopArmedRef.current = true;
      if (container.scrollTop <= 200) handleLoadEarlier();
    };

    const syncFrameMetrics = () => {
      if (isRestoringHistoryRef.current || isLoadingEarlier) return;
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

    // Initial load restores the bottom; only user scrolls trigger history loading.
    syncFrameMetrics();

    const resizeObserver = new ResizeObserver(() => {
      syncFrameMetrics();
    });
    resizeObserver.observe(container);
    if (contentRef.current) {
      resizeObserver.observe(contentRef.current);
    }

    container.addEventListener("scroll", handleScroll, { passive: true });
    container.addEventListener("wheel", handleHistoryIntent, { passive: true });
    container.addEventListener("touchmove", handleHistoryIntent, { passive: true });
    return () => {
      if (restoreScrollRafRef.current !== null) {
        window.cancelAnimationFrame(restoreScrollRafRef.current);
        restoreScrollRafRef.current = null;
      }
      resizeObserver.disconnect();
      container.removeEventListener("scroll", handleScroll);
      container.removeEventListener("wheel", handleHistoryIntent);
      container.removeEventListener("touchmove", handleHistoryIntent);
    };
  }, [
    isRunning,
    onAtBottomChange,
    scheduleLoadedSessionBottomRestore,
    scheduleStreamingScrollToBottom,
    captureHistoryAnchor,
    handleLoadEarlier,
    isLoadingEarlier,
    cancelHistoryRestore,
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

  useEffect(() => {
    onAtBottomChange?.(isAtBottomRef.current);
  }, [onAtBottomChange]);

  useEffect(() => {
    if (!scrollToBottomFnRef) return;
    scrollToBottomFnRef.current = () => {
      const container = getScrollContainer();
      if (!(container instanceof HTMLElement)) return;
      cancelHistoryRestore();
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
  }, [
    scrollToBottomFnRef,
    getScrollContainer,
    scrollContainerToBottom,
    onAtBottomChange,
    cancelHistoryRestore,
  ]);

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
      if (historyRestoreRafRef.current !== null)
        window.cancelAnimationFrame(historyRestoreRafRef.current);
      if (historyLoadRafRef.current !== null)
        window.cancelAnimationFrame(historyLoadRafRef.current);
      isRestoringLoadedSessionBottomRef.current = false;
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
  const [blockState, setBlockState] = useState(() => ({
    messages: displayMessages,
    closeOpenNodeAt,
    blocks: buildAgentMessageBlocks(displayMessages, { closeOpenNodeAt }),
  }));
  let messageBlocks = blockState.blocks;
  if (blockState.messages !== displayMessages || blockState.closeOpenNodeAt !== closeOpenNodeAt) {
    messageBlocks = buildAgentMessageBlocks(displayMessages, {
      closeOpenNodeAt,
      previousBlocks: blockState.blocks,
    });
    setBlockState({ messages: displayMessages, closeOpenNodeAt, blocks: messageBlocks });
  }
  const visibleMessageBlocks = useMemo(
    () => getVisibleAgentMessageBlocks(messageBlocks, collapsedNodeIds),
    [collapsedNodeIds, messageBlocks],
  );
  visibleBlocksRef.current = visibleMessageBlocks;
  const layoutKey = `${scrollToBottomKey ?? ""}:${visibleMessageBlocks.length > 0}`;
  useLayoutEffect(() => {
    if (lastLoadScrollKeyRef.current !== layoutKey) {
      lastLoadScrollKeyRef.current = layoutKey;
      pendingLoadedSessionRestoreKeyRef.current = layoutKey;
      isRestoringLoadedSessionBottomRef.current = true;
      shouldFollowBottomRef.current = true;
    }
    if (visibleMessageBlocks.length === 0) {
      isRestoringLoadedSessionBottomRef.current = false;
      pendingLoadedSessionRestoreKeyRef.current = null;
      return;
    }
    scheduleLoadedSessionBottomRestore();
  }, [layoutKey, scheduleLoadedSessionBottomRestore, visibleMessageBlocks]);
  const [historyPosition, setHistoryPosition] = useState({
    blocks: visibleMessageBlocks,
    messages,
    generation: historyGeneration,
    firstItemIndex: INITIAL_FIRST_ITEM_INDEX,
  });
  let firstItemIndex = historyPosition.firstItemIndex;
  if (
    historyPosition.blocks !== visibleMessageBlocks ||
    historyPosition.generation !== historyGeneration
  ) {
    const isPrepend =
      historyPosition.messages[0]?.id !== messages[0]?.id &&
      messages.some((message) => message.id === historyPosition.messages[0]?.id);
    firstItemIndex -=
      historyPosition.generation === historyGeneration && isPrepend
        ? getPrependedBlockCount(historyPosition.blocks, visibleMessageBlocks)
        : 0;
    setHistoryPosition({
      blocks: visibleMessageBlocks,
      messages,
      generation: historyGeneration,
      firstItemIndex,
    });
  }

  const hasPendingHistoryPrepend = Boolean(
    historyAnchorRef.current &&
    historyAnchorRef.current.generation === historyGeneration &&
    historyAnchorRef.current.messages[0]?.id !== messages[0]?.id &&
    !isRollbacking &&
    !hasEarlierError,
  );
  const showHistoryLoading = isLoadingEarlier || isRestoringHistory || hasPendingHistoryPrepend;

  useLayoutEffect(() => {
    const anchor = historyAnchorRef.current;
    if (!anchor) return;
    if (anchor.generation !== historyGeneration || isRollbacking || hasEarlierError) {
      historyAnchorRef.current = null;
      isRestoringHistoryRef.current = false;
      setIsRestoringHistory(false);
      if (historyRestoreRafRef.current !== null)
        window.cancelAnimationFrame(historyRestoreRafRef.current);
      historyRestoreRafRef.current = null;
      return;
    }
    if (isLoadingEarlier) {
      captureHistoryAnchor();
      return;
    }
    if (anchor.messages === messages) return;
    // Streaming append is not a history prepend.
    if (anchor.messages[0]?.id === messages[0]?.id) {
      historyAnchorRef.current = null;
      setIsRestoringHistory(false);
      return;
    }
    let blockIndex = visibleMessageBlocks.findIndex((block) =>
      block.messages.some((message) => message.id === anchor.id),
    );
    if (blockIndex < 0) {
      // A repeated node header can disappear when the boundary node is merged.
      const fallback = anchor.fallbacks.find((item) =>
        visibleMessageBlocks.some((block) =>
          block.messages.some((message) => message.id === item.id),
        ),
      );
      if (fallback) {
        anchor.id = fallback.id;
        anchor.top = fallback.top;
        blockIndex = visibleMessageBlocks.findIndex((block) =>
          block.messages.some((message) => message.id === anchor.id),
        );
      }
    }
    if (blockIndex < 0) {
      historyAnchorRef.current = null;
      setIsRestoringHistory(false);
      return;
    }
    const previousBlock = anchor.blocks.find((block) =>
      block.messages.some((message) => message.id === anchor.id),
    );
    const isBoundaryExpanded =
      previousBlock !== undefined &&
      previousBlock.messages[0]?.id !== visibleMessageBlocks[blockIndex].messages[0]?.id;
    isRestoringHistoryRef.current = true;
    setIsRestoringHistory(true);
    shouldFollowBottomRef.current = false;
    let attempts = 0;
    let stableFrames = 0;
    let isAnchorMissing = false;
    let isAnchorScrollPending = false;
    let previousScrollHeight = -1;
    let isFinished = false;
    const restore = (isResizeNotification = false) => {
      if (isFinished) return;
      if (historyRestoreRafRef.current !== null)
        window.cancelAnimationFrame(historyRestoreRafRef.current);
      historyRestoreRafRef.current = null;
      const container = scrollContainerRef.current;
      if (!container || historyAnchorRef.current !== anchor) {
        isFinished = true;
        resizeObserver.disconnect();
        return;
      }
      attempts += 1;
      const elements = contentRef.current?.querySelectorAll<HTMLElement>(
        "[data-scroll-message-ids]",
      );
      const element = Array.from(elements ?? []).findLast(
        (item) =>
          !item.closest('[aria-hidden="true"], [inert]') &&
          (JSON.parse(item.dataset.scrollMessageIds ?? "[]") as string[]).includes(anchor.id),
      );
      if (prependOffsetRef.current !== 0 || isAnchorScrollPending) {
        stableFrames = 0;
      } else if (
        element &&
        element.getBoundingClientRect().height > 0 &&
        window.getComputedStyle(element).visibility === "visible"
      ) {
        isAnchorMissing = false;
        const delta =
          element.getBoundingClientRect().top - container.getBoundingClientRect().top - anchor.top;
        // The list's temporary prepend deviation has already been cleared at this point.
        if (Math.abs(delta) > 1) {
          const blockElement = element.closest<HTMLElement>("[data-message-block-index]");
          if (blockElement) {
            const offset =
              element.getBoundingClientRect().top -
              blockElement.getBoundingClientRect().top -
              anchor.top;
            isAnchorScrollPending = true;
            virtuosoRef.current?.scrollIntoView({
              index: blockIndex,
              calculateViewLocation: () => ({ index: blockIndex, align: "start", offset }),
              done: () => {
                isAnchorScrollPending = false;
                if (isFinished || historyAnchorRef.current !== anchor || !element.isConnected)
                  return;
                container.scrollTop +=
                  element.getBoundingClientRect().top -
                  container.getBoundingClientRect().top -
                  anchor.top;
              },
            });
          }
          stableFrames = 0;
        } else if (container.scrollHeight === previousScrollHeight) {
          if (!isResizeNotification) stableFrames += 1;
        } else stableFrames = 0;
      } else {
        stableFrames = 0;
        if (isBoundaryExpanded && !element && !isAnchorMissing) {
          isAnchorMissing = true;
          virtuosoRef.current?.scrollToIndex({
            index: blockIndex,
            align: "start",
            offset: -anchor.top,
          });
        }
      }
      previousScrollHeight = container.scrollHeight;
      if (stableFrames >= 6 || attempts >= MAX_BOTTOM_RESTORE_ATTEMPTS) {
        isFinished = true;
        resizeObserver.disconnect();
        historyResizeObserverRef.current = null;
        historyAnchorRef.current = null;
        isRestoringHistoryRef.current = false;
        setIsRestoringHistory(false);
        viewportMetricsRef.current = {
          scrollHeight: container.scrollHeight,
          scrollTop: container.scrollTop,
          clientHeight: container.clientHeight,
        };
        return;
      }
      historyRestoreRafRef.current = window.requestAnimationFrame(() => restore());
    };
    const resizeObserver = new ResizeObserver(() => restore(true));
    historyResizeObserverRef.current = resizeObserver;
    if (contentRef.current) resizeObserver.observe(contentRef.current);
    historyRestoreRafRef.current = window.requestAnimationFrame(() => restore());
    return () => {
      isFinished = true;
      resizeObserver.disconnect();
      historyResizeObserverRef.current = null;
      if (historyRestoreRafRef.current !== null)
        window.cancelAnimationFrame(historyRestoreRafRef.current);
      historyRestoreRafRef.current = null;
      isRestoringHistoryRef.current = false;
    };
  }, [
    captureHistoryAnchor,
    firstItemIndex,
    hasEarlierError,
    historyGeneration,
    isLoadingEarlier,
    isRollbacking,
    messages,
    visibleMessageBlocks,
  ]);

  useLayoutEffect(
    () => () => {
      if (historyLoadRafRef.current !== null)
        window.cancelAnimationFrame(historyLoadRafRef.current);
      historyLoadRafRef.current = null;
    },
    [historyGeneration, isRollbacking],
  );
  const navigationItems = useMemo(
    () => buildAgentMessageNavigationItems(messageBlocks, visibleMessageBlocks),
    [messageBlocks, visibleMessageBlocks],
  );
  const navigationBlockIndices = useMemo(
    () => navigationItems.map((item) => item.blockIndex),
    [navigationItems],
  );
  const changeSummaryByAnchorId = useMemo(
    () => buildAgentRoundChangeSummaries(messageBlocks, visibleMessageBlocks, changes, isRunning),
    [changes, isRunning, messageBlocks, visibleMessageBlocks],
  );
  const toolbarTargets = useMemo(
    () => getAgentRoundToolbarTargets(messageBlocks, visibleMessageBlocks, isRunning),
    [messageBlocks, visibleMessageBlocks, isRunning],
  );
  const toolbarTargetByAnchorId = useMemo(
    () => new Map(toolbarTargets.map((target) => [target.anchorBlockId, target])),
    [toolbarTargets],
  );

  useEffect(() => {
    setActiveNavigationIndex((current) => {
      if (navigationItems.length === 0) return 0;
      return Math.min(current, navigationItems.length - 1);
    });
  }, [navigationItems.length]);

  useEffect(() => {
    const container = getScrollContainer();
    if (!(container instanceof HTMLElement)) return;

    const updateActiveNavigationItem = () => {
      if (navigationBlockIndices.length === 0) return;
      const containerTop = container.getBoundingClientRect().top;
      const renderedBlocks = contentRef.current?.querySelectorAll<HTMLElement>(
        "[data-message-block-index]",
      );
      if (!renderedBlocks?.length) return;

      let firstVisibleBlockIndex: number | null = null;
      for (const block of renderedBlocks) {
        const blockIndex = Number(block.dataset.messageBlockIndex);
        if (!Number.isInteger(blockIndex)) continue;
        if (block.getBoundingClientRect().bottom > containerTop + 12) {
          firstVisibleBlockIndex = blockIndex;
          break;
        }
      }
      if (firstVisibleBlockIndex === null) return;

      const nextActiveIndex = getActiveMessageNavigationIndex(
        navigationBlockIndices,
        firstVisibleBlockIndex,
      );
      setActiveNavigationIndex((current) =>
        current === nextActiveIndex ? current : nextActiveIndex,
      );
    };

    updateActiveNavigationItem();
    container.addEventListener("scroll", updateActiveNavigationItem, { passive: true });
    return () => container.removeEventListener("scroll", updateActiveNavigationItem);
  }, [getScrollContainer, navigationBlockIndices, visibleMessageBlocks]);

  const toggleNodeCollapsed = useCallback((nodeId: string) => {
    setCollapsedNodeIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const navigateToMessage = useCallback(
    (blockIndex: number) => {
      cancelHistoryRestore();
      shouldFollowBottomRef.current = false;
      virtuosoRef.current?.scrollToIndex({
        index: blockIndex,
        align: "start",
        behavior: "smooth",
      });
    },
    [cancelHistoryRestore],
  );

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

  const renderBlock = (block: AgentMessageBlock, blockIndex: number) => {
    const toolbarTarget = toolbarTargetByAnchorId.get(block.id);
    const changeSummary = changeSummaryByAnchorId.get(block.id);
    if (block.type === "node") {
      const message = block.messages[0];
      if (!message || message.type !== "node_start") return null;
      const nodeId = block.nodeId ?? message.id;
      const isCollapsed = collapsedNodeIds.has(nodeId);
      return (
        <Box
          className="agent-message-block-stack"
          data-block-type="node"
          data-message-block-index={blockIndex}
          data-scroll-message-ids={JSON.stringify([message.id])}
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
          {changeSummary ? (
            <AgentChangeSummaryCard
              summary={changeSummary}
              onOpenChanges={
                onOpenChanges
                  ? () =>
                      onOpenChanges(
                        changeSummary,
                        changeSummary.items.find((item) => item.revisionId)?.revisionId,
                      )
                  : undefined
              }
            />
          ) : null}
          {toolbarTarget ? renderAgentRoundToolbar(toolbarTarget) : null}
        </Box>
      );
    }

    if (block.type === "user") {
      const message = block.messages[0];
      if (!message || message.type !== "user_request") return null;
      const canShowRollback = isRollbackableUserMessage(message) && !isRollbacking && !isRunning;
      const copyActionId = `copy:${block.id}`;
      const isCopied = copiedActionId === copyActionId;
      const timestampText = formatAgentToolbarTimestamp(message.timestamp);
      return (
        <Box
          className="agent-message-block"
          data-block-type="user"
          data-message-block-index={blockIndex}
          data-scroll-message-ids={JSON.stringify([message.id])}
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
                  copyText(message.content ?? "", t("assistant.noUserMessageToCopy"), copyActionId)
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
        className="agent-message-block-stack"
        data-block-type="agent"
        data-message-block-index={blockIndex}
      >
        <Box
          className="agent-message-block"
          data-block-type="agent"
        >
          <AgentBlockContent
            messages={block.messages}
            onOpenMentionChapter={onOpenMentionChapter}
            onAbortRetry={onAbortRetry}
          />
        </Box>
        {changeSummary ? (
          <AgentChangeSummaryCard
            summary={changeSummary}
            onOpenChanges={
              onOpenChanges
                ? () =>
                    onOpenChanges(
                      changeSummary,
                      changeSummary.items.find((item) => item.revisionId)?.revisionId,
                    )
                : undefined
            }
          />
        ) : null}
        {toolbarTarget ? renderAgentRoundToolbar(toolbarTarget) : null}
      </Box>
    );
  };

  const [scrollParent, setScrollParent] = useState<HTMLElement | null>(null);
  useLayoutEffect(() => {
    const container = contentRef.current?.closest(".ai-sidebar-messages");
    if (!(container instanceof HTMLElement)) return;
    scrollContainerRef.current = container;
    setScrollParent(container);
    if (isRestoringLoadedSessionBottomRef.current) {
      scheduleLoadedSessionBottomRestore();
    }
  }, [scheduleLoadedSessionBottomRestore]);

  const heightEstimates = useMemo(
    () =>
      visibleMessageBlocks.map((block) =>
        estimateAgentBlockHeight(block, changeSummaryByAnchorId.has(block.id)),
      ),
    [changeSummaryByAnchorId, visibleMessageBlocks],
  );
  const prependViewportBuffer =
    hasPendingHistoryPrepend && historyAnchorRef.current
      ? heightEstimates
          .slice(
            0,
            Math.max(
              0,
              getPrependedBlockCount(historyAnchorRef.current.blocks, visibleMessageBlocks),
            ),
          )
          .reduce((height, estimate) => height + estimate, 600)
      : 600;

  const footerContext = useMemo<AgentMessagesFooterContext>(
    () => ({
      statusMessage,
      showStatus:
        (status === "running" || status === "waiting_answer" || status === "waiting_approval") &&
        Boolean(statusMessage),
      roundStartedAt,
      bottomRef,
      scrollParent,
      onLoadingChange,
      showHistoryLoading,
      hasEarlierError,
      isRollbacking,
      onLoadEarlier: handleLoadEarlier,
      prependOffsetRef,
      onHistoryHeaderGrow: handleHistoryHeaderGrow,
    }),
    [
      handleHistoryHeaderGrow,
      handleLoadEarlier,
      hasEarlierError,
      isRollbacking,
      onLoadingChange,
      roundStartedAt,
      scrollParent,
      showHistoryLoading,
      status,
      statusMessage,
    ],
  );

  return (
    <Box
      className="agent-messages-root"
      data-rollbacking={isRollbacking ? "true" : undefined}
    >
      <AgentMessageNavigation
        items={navigationItems}
        activeIndex={activeNavigationIndex}
        onNavigate={navigateToMessage}
      />
      <Box
        ref={contentRef}
        className="agent-message-scroll-content"
      >
        {scrollParent ? (
          <Virtuoso
            key={layoutKey}
            ref={virtuosoRef}
            customScrollParent={scrollParent}
            data={visibleMessageBlocks}
            firstItemIndex={firstItemIndex}
            heightEstimates={heightEstimates}
            initialTopMostItemIndex={{ index: "LAST", align: "end" }}
            skipAnimationFrameInResizeObserver
            computeItemKey={(_index, block) => block.id}
            itemContent={(_index, block) => renderBlock(block, _index - firstItemIndex)}
            increaseViewportBy={{ top: 600, bottom: prependViewportBuffer }}
            context={footerContext}
            components={{
              Header: AgentMessagesHeader,
              List: AgentMessagesList,
              Footer: AgentMessagesFooter,
            }}
          />
        ) : null}
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
