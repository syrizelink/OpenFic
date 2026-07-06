import { Badge, Box, Button, Callout, Flex, Tabs, Text } from "@radix-ui/themes";
import axios from "axios";
import { AlertTriangle, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { forwardRef, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import "./summary-panel.css";

import { toast } from "@/components";
import type {
  EnqueueSummaryRequest,
  MissingChapterSummaryItem,
  MissingLongTermSummaryItem,
  SkippedChapterSummaryItem,
} from "@/lib/api-client";
import { requestBackgroundSnapshot } from "@/lib/background-socket";

import { useEnqueueSummary, useSummaryPanel } from "../hooks/use-summaries";
import {
  buildSummaryProgressState,
  shouldShowSummaryProgressPanel,
  type SummaryProgressState,
} from "../lib/summary-progress-state";

interface ApiErrorPayload {
  detail?: unknown;
  message?: unknown;
}

interface ChapterMaintenanceItem {
  key: string;
  request: EnqueueSummaryRequest;
  title: string;
  volumeTitle: string | null;
  status: MissingChapterSummaryItem["status"];
  isStale: boolean;
  progressMessage: string | null;
}

interface LongTermMaintenanceItem {
  key: string;
  request: EnqueueSummaryRequest;
  title: string;
  volumeTitle: null;
  status: MissingLongTermSummaryItem["status"];
  isStale: boolean;
  progressMessage: string | null;
}

type MaintenanceTab = "chapter" | "long_term" | "skipped";

function getErrorText(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (Array.isArray(value) && value.length > 0) return "请求参数不正确";
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
  return "摘要生成失败，请稍后重试。";
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

const STATUS_LABELS: Record<string, string> = {
  not_generated: "未生成",
  queued: "排队中",
  running: "正在生成",
  ready: "就绪",
  failed: "失败",
};

function SummaryStatusBadge({ status, isStale }: { status: string; isStale: boolean }) {
  const label = status === "ready" && isStale ? "待更新" : (STATUS_LABELS[status] ?? status);
  return <Badge color={getStatusColor(status, isStale)}>{label}</Badge>;
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
              {state.currentMessage}
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
            队列共 {state.totalCount} 项
          </Text>
          <Text
            size="1"
            color="gray"
          >
            已完成 {state.completedCount} 项
          </Text>
          <Text
            size="1"
            color="gray"
          >
            运行中 {state.runningCount} 项
          </Text>
          <Text
            size="1"
            color="gray"
          >
            排队中 {state.queuedCount} 项
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
    volumeTitle: item.volumeTitle,
    status: item.status,
    isStale: item.isStale,
    progressMessage: item.progressMessage,
  }));
}

function buildLongTermItems(
  longTermItems: MissingLongTermSummaryItem[],
): LongTermMaintenanceItem[] {
  return longTermItems.map((item) => ({
    key: `${item.startOrder}-${item.endOrder}`,
    request: { summaryType: "long_term", startOrder: item.startOrder, endOrder: item.endOrder },
    title: `${item.startOrder} - ${item.endOrder}`,
    volumeTitle: null,
    status: item.status,
    isStale: item.isStale,
    progressMessage: item.progressMessage,
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
            direction="column"
            gap="1"
            className="summary-row-fill"
          >
            <Text
              size="2"
              className="summary-maintenance-title"
            >
              {item.title}
            </Text>
            {item.volumeTitle && (
              <Text
                size="1"
                color="gray"
                className="summary-volume-label"
              >
                {item.volumeTitle}
              </Text>
            )}
          </Flex>
          <Flex
            align="center"
            gap="2"
            className="summary-row-fixed"
          >
            {item.progressMessage ? (
              <Text
                size="1"
                color="gray"
                className="summary-maintenance-progress-text"
              >
                {item.progressMessage}
              </Text>
            ) : null}
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
              生成
            </Button>
          </Flex>
        </Flex>
      </Box>
    </motion.div>
  );
});

function SkippedChapterList({ items }: { items: SkippedChapterSummaryItem[] }) {
  return (
    <Flex
      direction="column"
      gap="3"
    >
      <Flex
        align="center"
        justify="between"
        gap="3"
        wrap="wrap"
      >
        <Flex
          direction="column"
          gap="1"
        >
          <Text
            size="2"
            weight="medium"
          >
            已跳过章节
          </Text>
          <Text
            size="1"
            color="gray"
          >
            字数少于 500 的章节不会参与章节摘要生成，也不会阻塞区间摘要聚合。
          </Text>
        </Flex>
        <Badge color={items.length ? "gray" : "green"}>{items.length}</Badge>
      </Flex>

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
                  direction="column"
                  gap="1"
                  className="summary-row-fill"
                >
                  <Text
                    size="2"
                    className="summary-single-line-text"
                  >
                    {item.volumeTitle && (
                      <span className="summary-volume-label">{item.volumeTitle}</span>
                    )}
                    {item.chapterOrder}. {item.chapterTitle}
                  </Text>
                  <Text
                    size="1"
                    color="gray"
                  >
                    当前字数 {item.wordCount}
                  </Text>
                </Flex>
                <Badge color="gray">不参与摘要</Badge>
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
            当前没有因字数不足而跳过的章节。
          </Text>
        </Flex>
      )}

      {items.length > 20 && (
        <Text
          size="1"
          color="gray"
        >
          还有 {items.length - 20} 项未展开显示。
        </Text>
      )}
    </Flex>
  );
}

function MaintenanceList({
  title,
  totalText,
  emptyText,
  items,
  isGenerating,
  onGenerate,
}: {
  title: string;
  totalText: string;
  emptyText: string;
  items: Array<ChapterMaintenanceItem | LongTermMaintenanceItem>;
  isGenerating: boolean;
  onGenerate: (request: EnqueueSummaryRequest) => void;
}) {
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
      <Flex
        align="center"
        justify="between"
        gap="3"
        wrap="wrap"
      >
        <Flex
          direction="column"
          gap="1"
        >
          <Text
            size="2"
            weight="medium"
          >
            {title}
          </Text>
          <Text
            size="1"
            color="gray"
          >
            {totalText}
          </Text>
        </Flex>
        <Badge color={items.length ? "amber" : "green"}>{items.length}</Badge>
      </Flex>

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
          还有 {items.length - 20} 项会在批量生成时继续处理。
        </Text>
      )}
    </Flex>
  );
}

interface SummaryMaintenanceViewProps {
  projectId: string;
}

export function SummaryMaintenanceView({ projectId }: SummaryMaintenanceViewProps) {
  const { t } = useTranslation();
  const { data: panelData } = useSummaryPanel(projectId);
  const enqueueMutation = useEnqueueSummary(projectId);
  const [activeTab, setActiveTab] = useState<MaintenanceTab>("chapter");

  useEffect(() => {
    void requestBackgroundSnapshot(projectId).catch(() => undefined);
  }, [projectId]);

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
            {maintenance.blockReason ?? t("summary.maintenance.blockReasonFallback")}
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
            <Button
              size="2"
              onClick={handleGenerateAll}
              disabled={isGenerating || total === 0}
            >
              <Sparkles size={15} />
              {t("summary.maintenance.generateAll")}
            </Button>
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
              title={t("summary.maintenance.chapterQueueTitle")}
              totalText={t("summary.maintenance.chapterQueueDescription")}
              emptyText={t("summary.maintenance.chapterQueueEmpty")}
              items={chapterViewItems}
              isGenerating={isGenerating}
              onGenerate={handleGenerateOne}
            />
          </Tabs.Content>

          <Tabs.Content value="long_term">
            <MaintenanceList
              title={t("summary.maintenance.rangeQueueTitle")}
              totalText={t("summary.maintenance.rangeQueueDescription")}
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
