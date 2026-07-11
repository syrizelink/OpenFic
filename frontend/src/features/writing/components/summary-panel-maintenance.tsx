import { Badge, Box, Button, Callout, Flex, Tabs, Text } from "@radix-ui/themes";
import axios from "axios";
import { AlertTriangle, Play, Square } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { forwardRef, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import "./summary-panel.css";

import { Spinner, toast } from "@/components";
import type {
  EnqueueSummaryRequest,
  MissingChapterSummaryItem,
  MissingLongTermSummaryItem,
  SkippedChapterSummaryItem,
} from "@/lib/api-client";
import { requestBackgroundSnapshot } from "@/lib/background-socket";
import i18n from "@/i18n";

import {
  useCancelSummaryBatch,
  useEnqueueSummary,
  useSummaryPanel,
} from "../hooks/use-summaries";
import {
  buildSummaryProgressState,
  shouldShowSummaryProgressPanel,
  type SummaryProgressState,
} from "../lib/summary-progress-state";
import { formatSummaryRangeMeta } from "../lib/summary-range-title";

interface ApiErrorPayload {
  detail?: unknown;
  message?: unknown;
}

interface ChapterMaintenanceItem {
  key: string;
  request: EnqueueSummaryRequest;
  title: string;
  chapterOrder: number;
  volumeTitle: string | null;
  wordCount: number;
  status: MissingChapterSummaryItem["status"];
  isStale: boolean;
}

interface LongTermMaintenanceItem {
  key: string;
  request: EnqueueSummaryRequest;
  startOrder: number;
  startVolumeTitle: string | null;
  startChapterTitle: string;
  endOrder: number;
  endVolumeTitle: string | null;
  endChapterTitle: string;
  status: MissingLongTermSummaryItem["status"];
  isStale: boolean;
}

type MaintenanceTab = "chapter" | "long_term" | "skipped";

function getErrorText(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (Array.isArray(value) && value.length > 0) return i18n.t("summary.errorInvalidParams");
  return null;
}

function getSummaryErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const responseMessage =
      getErrorText(error.response?.data?.detail) ?? getErrorText(error.response?.data?.message);
    if (responseMessage) return responseMessage;
    if (error.message) return error.message;
  }

  if (error instanceof Error && error.message) return error.message;
  return i18n.t("summary.generateFailedFallback");
}

function getStatusColor(
  status: string,
  isStale: boolean,
): "green" | "blue" | "amber" | "red" | "gray" {
  if (status === "ready" && isStale) return "amber";
  if (status === "ready") return "green";
  if (status === "running") return "blue";
  if (status === "failed") return "red";
  if (status === "queued") return "amber";
  return "gray";
}

function SummaryStatusBadge({ status, isStale }: { status: string; isStale: boolean }) {
  const { t } = useTranslation();
  const label =
    status === "ready" && isStale
      ? t("summary.maintenance.status.stale")
      : t(`summary.maintenance.status.${status}`, { defaultValue: status });
  return <Badge color={getStatusColor(status, isStale)}>{label}</Badge>;
}

function translateProgressMessage(code: string | null, t: (key: string, options?: Record<string, unknown>) => string): string {
  if (!code) return "";
  return t(`summary.maintenance.progressMessages.${code}`, { defaultValue: code });
}

function AnimatedProgressBar({ value }: { value: number | null }) {
  const clampedValue = value == null ? null : Math.max(0, Math.min(100, value));

  return (
    <Box className="summary-progress-track">
      {clampedValue == null ? (
        <motion.div
          initial={{ x: "-35%" }}
          animate={{ x: ["-35%", "135%"] }}
          transition={{ duration: 1.1, ease: "easeInOut", repeat: Number.POSITIVE_INFINITY }}
          className="summary-progress-bar summary-progress-bar--indeterminate"
        />
      ) : (
        <div
          style={{ width: `${clampedValue}%` }}
          className="summary-progress-bar"
        />
      )}
    </Box>
  );
}

function SummaryProgressPanel({ state }: { state: SummaryProgressState }) {
  const { t } = useTranslation();
  return (
    <motion.div
      initial={{ opacity: 0, height: 0, y: -8 }}
      animate={{ opacity: 1, height: "auto", y: 0 }}
      exit={{ opacity: 0, height: 0, y: -8 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      className="summary-motion-hidden"
    >
      <Flex
        direction="column"
        gap="3"
        pt="1"
      >
        <Flex
          direction="column"
          gap="2"
        >
          <AnimatedProgressBar value={state.currentProgressValue} />
          <Flex
            align="center"
            justify="between"
            gap="3"
          >
            <Text
              size="1"
              color="gray"
            >
              {translateProgressMessage(state.currentMessage, t)}
            </Text>
            <Text
              size="1"
              color="gray"
            >
              {state.currentProgressValue == null ? "--" : `${state.currentProgressValue}%`}
            </Text>
          </Flex>
        </Flex>

        <Flex
          align="center"
          gap="3"
          wrap="wrap"
        >
          <Text
            size="1"
            color="gray"
          >
            {t("summary.maintenance.queueTotal", { count: state.totalCount })}
          </Text>
          <Text
            size="1"
            color="gray"
          >
            {t("summary.maintenance.queueCompleted", { count: state.completedCount })}
          </Text>
          <Text
            size="1"
            color="gray"
          >
            {t("summary.maintenance.queueRunning", { count: state.runningCount })}
          </Text>
          <Text
            size="1"
            color="gray"
          >
            {t("summary.maintenance.queueQueued", { count: state.queuedCount })}
          </Text>
        </Flex>
      </Flex>
    </motion.div>
  );
}

function buildChapterItems(chapterItems: MissingChapterSummaryItem[]): ChapterMaintenanceItem[] {
  return chapterItems.map((item) => ({
    key: item.chapterId,
    request: { summaryType: "chapter", chapterId: item.chapterId },
    title: item.chapterTitle,
    chapterOrder: item.chapterOrder,
    volumeTitle: item.volumeTitle,
    wordCount: item.wordCount,
    status: item.status,
    isStale: item.isStale,
  }));
}

function buildLongTermItems(
  longTermItems: MissingLongTermSummaryItem[],
): LongTermMaintenanceItem[] {
  return longTermItems.map((item) => ({
    key: `${item.startOrder}-${item.endOrder}`,
    request: { summaryType: "long_term", startOrder: item.startOrder, endOrder: item.endOrder },
    startOrder: item.startOrder,
    startVolumeTitle: item.startVolumeTitle,
    startChapterTitle: item.startChapterTitle,
    endOrder: item.endOrder,
    endVolumeTitle: item.endVolumeTitle,
    endChapterTitle: item.endChapterTitle,
    status: item.status,
    isStale: item.isStale,
  }));
}

interface MaintenanceRowProps {
  item: ChapterMaintenanceItem | LongTermMaintenanceItem;
  disabled: boolean;
  onGenerate: () => void;
}

const MaintenanceRow = forwardRef<HTMLDivElement, MaintenanceRowProps>(function MaintenanceRow(
  { item, disabled, onGenerate },
  ref,
) {
  const { t } = useTranslation();
  const isChapter = "chapterOrder" in item;
  return (
    <motion.div
      ref={ref}
      layout
      initial={{ opacity: 0, y: 8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 48, scale: 0.98 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1], layout: { duration: 0.24 } }}
      className="summary-motion-hidden"
    >
      <Box className="summary-card">
        <Flex
          align="center"
          justify="between"
          gap="3"
          px="3"
          py="2"
          className="summary-row"
        >
          <Flex
            align="center"
            gap="2"
            className="summary-row-fill"
          >
            <Text
              size="2"
              className="summary-maintenance-title"
            >
              {isChapter ? (
                <>
                  {item.volumeTitle && (
                    <span className="summary-volume-meta">
                      {item.volumeTitle} | {item.chapterOrder}
                    </span>
                  )}
                  {item.title}
                </>
              ) : (
                <>
                  {item.startVolumeTitle && (
                    <span className="summary-volume-meta">
                      {formatSummaryRangeMeta({
                        volumeTitle: item.startVolumeTitle,
                        chapterOrder: item.startOrder,
                      })}
                    </span>
                  )}
                  {!item.startVolumeTitle && `${item.startOrder}. `}
                  {item.startChapterTitle}
                  <span className="summary-range-separator"> - </span>
                  {item.endVolumeTitle && (
                    <span className="summary-volume-meta">
                      {formatSummaryRangeMeta({
                        volumeTitle: item.endVolumeTitle,
                        chapterOrder: item.endOrder,
                      })}
                    </span>
                  )}
                  {!item.endVolumeTitle && `${item.endOrder}. `}
                  {item.endChapterTitle}
                </>
              )}
            </Text>
            {isChapter && (
              <Badge
                variant="soft"
                color="gray"
                className="summary-word-count-badge"
              >
                {t("summary.wordCountWithUnit", { count: item.wordCount })}
              </Badge>
            )}
          </Flex>
          <Flex
            align="center"
            gap="2"
            className="summary-row-fixed"
          >
            <SummaryStatusBadge
              status={item.status}
              isStale={item.isStale}
            />
            <Button
              size="1"
              variant="soft"
              onClick={onGenerate}
              disabled={disabled}
            >
              {t("summary.maintenance.generate")}
            </Button>
          </Flex>
        </Flex>
      </Box>
    </motion.div>
  );
});

function SkippedChapterList({ items }: { items: SkippedChapterSummaryItem[] }) {
  const { t } = useTranslation();
  return (
    <Flex
      direction="column"
      gap="3"
    >
      {items.length ? (
        <Flex
          direction="column"
          gap="2"
        >
          {items.slice(0, 20).map((item) => (
            <Box
              key={item.chapterId}
              className="summary-card"
            >
              <Flex
                align="center"
                justify="between"
                gap="3"
                px="3"
                py="2"
                className="summary-row"
              >
                <Flex
                  align="center"
                  gap="2"
                  className="summary-row-fill"
                >
                  <Text
                    size="2"
                    className="summary-maintenance-title"
                  >
                    {item.volumeTitle && (
                      <span className="summary-volume-meta">
                        {item.volumeTitle} | {item.chapterOrder}
                      </span>
                    )}
                    {item.chapterTitle}
                  </Text>
                  <Badge
                    variant="soft"
                    color="gray"
                    className="summary-word-count-badge"
                  >
                    {t("summary.wordCountWithUnit", { count: item.wordCount })}
                  </Badge>
                </Flex>
                <Box className="summary-row-fixed">
                  <Badge color="gray">{t("summary.maintenance.skippedExcluded")}</Badge>
                </Box>
              </Flex>
            </Box>
          ))}
        </Flex>
      ) : (
        <Flex
          align="center"
          justify="center"
          py="8"
        >
          <Text
            size="2"
            color="gray"
          >
            {t("summary.maintenance.skippedEmpty")}
          </Text>
        </Flex>
      )}

      {items.length > 20 && (
        <Text
          size="1"
          color="gray"
        >
          {t("summary.maintenance.overflowHidden", { count: items.length - 20 })}
        </Text>
      )}
    </Flex>
  );
}

function MaintenanceList({
  emptyText,
  items,
  isGenerating,
  onGenerate,
}: {
  emptyText: string;
  items: Array<ChapterMaintenanceItem | LongTermMaintenanceItem>;
  isGenerating: boolean;
  onGenerate: (request: EnqueueSummaryRequest) => void;
}) {
  const { t } = useTranslation();
  const [displayedItems, setDisplayedItems] = useState(items);

  useEffect(() => {
    if (items.length === 0) return;
    const timer = window.setTimeout(() => {
      setDisplayedItems(items);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [items]);

  useEffect(() => {
    if (items.length > 0 || displayedItems.length === 0) return;
    if (items.length === 0) {
      const timer = window.setTimeout(() => {
        setDisplayedItems([]);
      }, 220);
      return () => window.clearTimeout(timer);
    }
  }, [displayedItems.length, items]);

  return (
    <Flex
      direction="column"
      gap="3"
    >
      {displayedItems.length ? (
        <Flex
          direction="column"
          gap="2"
        >
          <AnimatePresence
            initial={false}
            mode="popLayout"
          >
            {displayedItems.slice(0, 20).map((item) => {
              const isPresent = items.some((currentItem) => currentItem.key === item.key);
              return (
                <MaintenanceRow
                  key={item.key}
                  item={item}
                  disabled={isGenerating || !isPresent}
                  onGenerate={() => onGenerate(item.request)}
                />
              );
            })}
          </AnimatePresence>
        </Flex>
      ) : (
        <Flex
          align="center"
          justify="center"
          py="8"
        >
          <Text
            size="2"
            color="gray"
          >
            {emptyText}
          </Text>
        </Flex>
      )}

      {items.length > 20 && (
        <Text
          size="1"
          color="gray"
        >
          {t("summary.maintenance.overflowBatchRemaining", { count: items.length - 20 })}
        </Text>
      )}
    </Flex>
  );
}

interface SummaryMaintenanceViewProps {
  projectId: string;
  open: boolean;
}

export function SummaryMaintenanceView({ projectId, open }: SummaryMaintenanceViewProps) {
  const { t } = useTranslation();
  const { data: panelData } = useSummaryPanel(projectId);
  const enqueueMutation = useEnqueueSummary(projectId);
  const cancelBatchMutation = useCancelSummaryBatch(projectId);
  const [activeTab, setActiveTab] = useState<MaintenanceTab>("chapter");
  const [isRefreshing, setIsRefreshing] = useState(true);

  useEffect(() => {
    if (!open) return;
    setIsRefreshing(true);
    void requestBackgroundSnapshot(projectId)
      .catch(() => undefined)
      .finally(() => setIsRefreshing(false));
  }, [open, projectId]);

  const maintenance = panelData?.maintenance;
  const chapterItems = useMemo(
    () => maintenance?.missingOrFailedChapterSummaries ?? [],
    [maintenance],
  );
  const longTermItems = useMemo(
    () => maintenance?.missingOrFailedLongTermSummaries ?? [],
    [maintenance],
  );
  const skippedItems = useMemo(() => maintenance?.skippedChapterSummaries ?? [], [maintenance]);
  const batchProgress = useMemo(() => maintenance?.batchProgress ?? null, [maintenance]);
  const activeJobs = useMemo(() => maintenance?.activeJobs ?? [], [maintenance]);
  const total = chapterItems.length + longTermItems.length;
  const progressState = useMemo(
    () => buildSummaryProgressState(batchProgress, activeJobs),
    [activeJobs, batchProgress],
  );
  const isGenerating = enqueueMutation.isPending || (progressState?.isActive ?? false);
  const isCancelling = progressState?.status === "cancel_requested";
  const batchJobId = progressState?.isActive ? batchProgress?.jobId : null;

  const chapterViewItems = useMemo(() => buildChapterItems(chapterItems), [chapterItems]);
  const longTermViewItems = useMemo(() => buildLongTermItems(longTermItems), [longTermItems]);

  const handleGenerateOne = async (request: EnqueueSummaryRequest) => {
    try {
      await enqueueMutation.mutateAsync(request);
    } catch (error) {
      toast.error(t("summary.enqueueFailed", { reason: getSummaryErrorMessage(error) }));
    }
  };

  const handleGenerateAll = async () => {
    if (!maintenance) return;
    try {
      await enqueueMutation.mutateAsync({ summaryType: "all" });
    } catch (error) {
      toast.error(t("summary.batchEnqueueFailed", { reason: getSummaryErrorMessage(error) }));
    }
  };

  const handleStopGenerating = async () => {
    if (!batchJobId) return;
    try {
      await cancelBatchMutation.mutateAsync(batchJobId);
    } catch (error) {
      toast.error(t("summary.batchCancelFailed", { reason: getSummaryErrorMessage(error) }));
    }
  };

  if (isRefreshing) {
    return (
      <Flex
        align="center"
        justify="center"
        className="summary-panel-loading"
      >
        <Spinner size={24} />
      </Flex>
    );
  }

  return (
    <Flex
      direction="column"
      gap="4"
    >
      {maintenance?.autoGenerationBlocked && (
        <Callout.Root
          color="amber"
          size="1"
        >
          <Callout.Icon>
            <AlertTriangle size={16} />
          </Callout.Icon>
          <Callout.Text>
            {maintenance.blockReasonCode
              ? t(
                  `summary.maintenance.blockReasons.${maintenance.blockReasonCode}`,
                  maintenance.blockReasonParams ?? {},
                )
              : t("summary.maintenance.blockReasonFallback")}
          </Callout.Text>
        </Callout.Root>
      )}

      <Box
        p="4"
        className="summary-maintenance-hero"
      >
        <Flex
          direction="column"
          gap="3"
        >
          <Flex
            align="start"
            justify="between"
            gap="4"
          >
            <Flex
              direction="column"
              gap="1"
            >
              <Text
                size="3"
                weight="medium"
              >
                {t("summary.maintenance.queueTitle")}
              </Text>
              <Text
                size="2"
                color="gray"
              >
                {t("summary.maintenance.queueDescription", {
                  chapterCount: chapterItems.length,
                  rangeCount: longTermItems.length,
                })}
              </Text>
            </Flex>
            {isGenerating ? (
              <Button
                size="2"
                color="red"
                onClick={handleStopGenerating}
                disabled={!batchJobId || isCancelling || cancelBatchMutation.isPending}
              >
                <Square size={14} />
                {t("summary.maintenance.generateStop")}
              </Button>
            ) : (
              <Button
                size="2"
                onClick={handleGenerateAll}
                disabled={total === 0}
              >
                <Play size={15} />
                {t("summary.maintenance.generateStart")}
              </Button>
            )}
          </Flex>

          <Flex
            gap="2"
            wrap="wrap"
          >
            <Badge color={chapterItems.length ? "amber" : "green"}>
              {t("summary.maintenance.chapterBadge", { count: chapterItems.length })}
            </Badge>
            <Badge color={longTermItems.length ? "amber" : "green"}>
              {t("summary.maintenance.rangeBadge", { count: longTermItems.length })}
            </Badge>
            <Badge color={skippedItems.length ? "gray" : "green"}>
              {t("summary.maintenance.skippedBadge", { count: skippedItems.length })}
            </Badge>
            <Badge color={progressState?.isActive ? "amber" : "gray"}>
              {t("summary.maintenance.processingBadge", {
                count: progressState?.isActive ? (progressState.totalCount ?? 0) : 0,
              })}
            </Badge>
          </Flex>

          <AnimatePresence
            initial={false}
            mode="wait"
          >
            {shouldShowSummaryProgressPanel(progressState) ? (
              <SummaryProgressPanel
                key="summary-progress"
                state={progressState}
              />
            ) : null}
          </AnimatePresence>
        </Flex>
      </Box>

      <Tabs.Root
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as MaintenanceTab)}
      >
        <Tabs.List>
          <Tabs.Trigger value="chapter">
            <Flex
              align="center"
              gap="2"
            >
              <Text size="2">{t("summary.tabs.chapters")}</Text>
              <Badge color={chapterViewItems.length ? "amber" : "green"}>
                {chapterViewItems.length}
              </Badge>
            </Flex>
          </Tabs.Trigger>
          <Tabs.Trigger value="long_term">
            <Flex
              align="center"
              gap="2"
            >
              <Text size="2">{t("summary.tabs.ranges")}</Text>
              <Badge color={longTermViewItems.length ? "amber" : "green"}>
                {longTermViewItems.length}
              </Badge>
            </Flex>
          </Tabs.Trigger>
          <Tabs.Trigger value="skipped">
            <Flex
              align="center"
              gap="2"
            >
              <Text size="2">{t("summary.maintenance.skippedChapters")}</Text>
              <Badge color={skippedItems.length ? "gray" : "green"}>{skippedItems.length}</Badge>
            </Flex>
          </Tabs.Trigger>
        </Tabs.List>

        <Box pt="4">
          <Tabs.Content value="chapter">
            <MaintenanceList
              emptyText={t("summary.maintenance.chapterQueueEmpty")}
              items={chapterViewItems}
              isGenerating={isGenerating}
              onGenerate={handleGenerateOne}
            />
          </Tabs.Content>

          <Tabs.Content value="long_term">
            <MaintenanceList
              emptyText={t("summary.maintenance.rangeQueueEmpty")}
              items={longTermViewItems}
              isGenerating={isGenerating}
              onGenerate={handleGenerateOne}
            />
          </Tabs.Content>

          <Tabs.Content value="skipped">
            <SkippedChapterList items={skippedItems} />
          </Tabs.Content>
        </Box>
      </Tabs.Root>
    </Flex>
  );
}
