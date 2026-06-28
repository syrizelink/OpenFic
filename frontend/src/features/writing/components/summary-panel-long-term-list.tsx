import { memo, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import axios from "axios";
import {
  Box,
  Checkbox,
  Flex,
  IconButton,
  Skeleton,
  Text,
  TextField,
  Tooltip,
} from "@radix-ui/themes";
import { ChevronDown, ChevronLeft, ChevronRight, ListChecks, Search, Trash2 } from "lucide-react";
import "./summary-panel.css";

import { ConfirmDialog, toast } from "@/components";
import type { LongTermSummaryListItem } from "@/lib/api-client";
import {
  useDeleteLongTermSummaries,
  useLongTermSummariesPage,
} from "../hooks/use-summaries";

const PAGE_SIZE = 20;

interface ApiErrorPayload {
  detail?: unknown;
  message?: unknown;
}

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
  return "摘要处理失败，请稍后重试。";
}

function getStatusColor(status: string, isStale: boolean): "green" | "blue" | "amber" | "red" | "gray" {
  if (status === "ready" && isStale) return "amber";
  if (status === "ready") return "green";
  if (status === "running") return "blue";
  if (status === "failed") return "red";
  if (status === "queued") return "amber";
  return "gray";
}

const STATUS_LABELS: Record<string, string> = {
  not_generated: "未显示",
  queued: "排队中",
  running: "正在生成",
  ready: "就绪",
  failed: "失败",
};

function SummaryStatusBadge({ status, isStale }: { status: string; isStale: boolean }) {
  const label = status === "ready" && isStale ? "待更新" : (STATUS_LABELS[status] ?? status);
  return (
    <span className="rt-Badge rt-r-size-1 rt-variant-soft" data-accent-color={getStatusColor(status, isStale)}>
      {label}
    </span>
  );
}

function getVisiblePages(currentPage: number, totalPages: number): Array<number | "ellipsis"> {
  if (totalPages <= 6) return Array.from({ length: totalPages }, (_, index) => index + 1);
  if (currentPage <= 3) return [1, 2, 3, "ellipsis", totalPages - 1, totalPages];
  if (currentPage >= totalPages - 2) return [1, 2, "ellipsis", totalPages - 2, totalPages - 1, totalPages];
  return [1, currentPage - 1, currentPage, "ellipsis", currentPage + 1, totalPages];
}

function LongTermSummarySkeletonList() {
  return (
    <Flex direction="column" gap="2">
      {Array.from({ length: PAGE_SIZE }, (_, index) => (
        <Box
          key={index}
          className="summary-card"
        >
          <Flex align="center" gap="3" px="3" py="2" className="summary-row">
            <Skeleton height="16px" width="16px" style={{ borderRadius: 999 }} />
            <Skeleton height="16px" width={`${34 + (index % 3) * 6}%`} style={{ maxWidth: 180 }} />
            <Box className="summary-row-fixed">
              <Skeleton height="20px" width="56px" style={{ borderRadius: 999 }} />
            </Box>
          </Flex>
        </Box>
      ))}
    </Flex>
  );
}

interface LongTermSummaryAccordionItemProps {
  item: LongTermSummaryListItem;
  expanded: boolean;
  selected: boolean;
  isSelecting: boolean;
  onToggleExpand: () => void;
  onToggleSelect: () => void;
}

function SummaryPaginationSkeleton() {
  return (
    <Flex align="center" justify="between" wrap="wrap" gap="3">
      <Skeleton height="16px" width="160px" />
      <Flex align="center" gap="2" wrap="wrap">
        <Skeleton height="16px" width="72px" />
        <Skeleton height="28px" width="52px" style={{ borderRadius: 999 }} />
        <Flex align="center" gap="1">
          <Skeleton height="28px" width="28px" style={{ borderRadius: 999 }} />
          <Skeleton height="28px" width="28px" style={{ borderRadius: 999 }} />
          <Skeleton height="28px" width="28px" style={{ borderRadius: 999 }} />
          <Skeleton height="28px" width="28px" style={{ borderRadius: 999 }} />
        </Flex>
        <Skeleton height="28px" width="52px" style={{ borderRadius: 999 }} />
      </Flex>
    </Flex>
  );
}

const LongTermSummaryAccordionItem = memo(function LongTermSummaryAccordionItem({
  item,
  expanded,
  selected,
  isSelecting,
  onToggleExpand,
  onToggleSelect,
}: LongTermSummaryAccordionItemProps) {
  const canExpand = item.status !== "not_generated";

  return (
    <Box
      className="summary-card"
      data-selected={selected ? "true" : "false"}
    >
      <Flex align="center" gap="3" px="3" py="2" className="summary-row">
        {isSelecting && <Checkbox checked={selected} onCheckedChange={onToggleSelect} />}
        <button
          type="button"
          onClick={canExpand ? onToggleExpand : undefined}
          disabled={!canExpand}
          className="summary-expand-button"
          data-expandable={canExpand ? "true" : "false"}
          aria-label={expanded ? "收起" : "展开"}
        >
          <ChevronDown size={14} className="summary-expand-icon" data-expanded={expanded ? "true" : "false"} />
        </button>
        <Text size="2" className="summary-range-title">
          {`第 ${item.startOrder} - ${item.endOrder} 章`}
        </Text>
        <Box className="summary-row-fixed">
          <SummaryStatusBadge status={item.status} isStale={item.isStale} />
        </Box>
      </Flex>
      <AnimatePresence initial={false}>
        {expanded && canExpand ? (
          <motion.div
            key="summary-content"
            className="summary-accordion-content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              height: { duration: 0.22, ease: [0.22, 1, 0.36, 1] },
              opacity: { duration: 0.18, ease: "easeOut" },
            }}
          >
            <Box className="summary-accordion-content__inner" px="3">
              <Flex direction="column" gap="2">
                {(item.startTime || item.endTime) && (
                  <Text size="1" color="gray">
                    {item.startTime || "未知"} - {item.endTime || "未知"}
                  </Text>
                )}
                <Text size="2" className="summary-content-text">
                  {item.summary || "该区间摘要尚未生成，当前先保留为未显示状态。"}
                </Text>
                {item.errorMessage && (
                  <Text size="1" color="red">
                    {item.errorMessage}
                  </Text>
                )}
              </Flex>
            </Box>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </Box>
  );
}, areLongTermSummaryItemPropsEqual);

function areLongTermSummaryItemPropsEqual(
  previous: Readonly<LongTermSummaryAccordionItemProps>,
  next: Readonly<LongTermSummaryAccordionItemProps>
) {
  return (
    previous.item === next.item &&
    previous.expanded === next.expanded &&
    previous.selected === next.selected &&
    previous.isSelecting === next.isSelecting
  );
}

interface LongTermSummaryListViewProps {
  projectId: string;
  open: boolean;
  emptyText: string;
}

export function LongTermSummaryListView({
  projectId,
  open,
  emptyText,
}: LongTermSummaryListViewProps) {
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedRanges, setSelectedRanges] = useState<string[]>([]);
  const [expandedRanges, setExpandedRanges] = useState<string[]>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const { data: pageData, isLoading, isFetching, refetch } = useLongTermSummariesPage(projectId, page);
  const deleteMutation = useDeleteLongTermSummaries(projectId);
  const requestPage = page;
  const isInitialLoading = isLoading && !pageData;
  const isPageSwitchLoading = isFetching && (pageData?.page ?? requestPage) !== requestPage;
  const isListLoading = isInitialLoading || isPageSwitchLoading;

  useEffect(() => {
    if (!open) return;
    void refetch();
  }, [open, refetch]);

  const items = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const source = pageData?.items ?? [];
    if (!query) return source;
    return source.filter((item) => {
      const haystack = [
        `${item.startOrder}`,
        `${item.endOrder}`,
        `第 ${item.startOrder} - ${item.endOrder} 章`,
        item.summary,
        item.errorMessage ?? "",
      ]
        .join("\n")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [pageData?.items, searchQuery]);

  const visibleRangeKeys = useMemo(
    () => new Set(items.map((item) => `${item.startOrder}-${item.endOrder}`)),
    [items]
  );
  const selectedKeys = useMemo(
    () => selectedRanges.filter((key) => visibleRangeKeys.has(key)),
    [selectedRanges, visibleRangeKeys]
  );
  const expandedKeys = useMemo(
    () => expandedRanges.filter((key) => visibleRangeKeys.has(key)),
    [expandedRanges, visibleRangeKeys]
  );
  const selectedKeySet = useMemo(() => new Set(selectedKeys), [selectedKeys]);
  const expandedKeySet = useMemo(() => new Set(expandedKeys), [expandedKeys]);
  const total = pageData?.total ?? 0;
  const pageSize = pageData?.pageSize ?? PAGE_SIZE;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(requestPage, totalPages);
  const visiblePages = useMemo(() => getVisiblePages(currentPage, totalPages), [currentPage, totalPages]);
  const pageStart = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const pageEnd = total === 0 ? 0 : Math.min(currentPage * pageSize, total);

  const handleToggleSelectionMode = () => {
    setIsSelectionMode((value) => {
      if (value) setSelectedRanges([]);
      return !value;
    });
  };

  const handleToggleSelect = (key: string) => {
    setSelectedRanges((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key]
    );
  };

  const handleToggleExpand = (key: string) => {
    setExpandedRanges((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key]
    );
  };

  const handleConfirmDelete = async () => {
    const targetRanges: Array<[number, number]> =
      isSelectionMode && selectedKeys.length > 0
        ? selectedKeys.map((key) => {
            const [s, e] = key.split("-").map(Number);
            return [s, e] as [number, number];
          })
        : [];
    try {
      const shouldGoToPreviousPage = items.length === 1 && currentPage > 1;
      await deleteMutation.mutateAsync(targetRanges);
      setDeleteDialogOpen(false);
      setSelectedRanges([]);
      setExpandedRanges([]);
      setIsSelectionMode(false);
      if (shouldGoToPreviousPage) {
        setPage((current) => current - 1);
      }
      toast.success(targetRanges.length > 0 ? "已删除选中的区间摘要。" : "已删除全部区间摘要。");
    } catch (error) {
      toast.error(`删除区间摘要失败：${getSummaryErrorMessage(error)}`);
    }
  };

  if (!isListLoading && !items.length && !searchQuery) {
    return (
      <Flex direction="column" align="center" justify="center" gap="2" py="8">
        <Text size="2" color="gray">
          {emptyText}
        </Text>
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap="3">
      <Flex align="center" gap="2">
        <TextField.Root
          placeholder="搜索章节区间或摘要内容"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          size="2"
          className="summary-search-input"
        >
          <TextField.Slot>
            <Search size={16} />
          </TextField.Slot>
        </TextField.Root>
        <Tooltip content={isSelectionMode ? "取消多选" : "多选"}>
          <IconButton variant={isSelectionMode ? "soft" : "ghost"} size="2" onClick={handleToggleSelectionMode}>
            <ListChecks size={16} />
          </IconButton>
        </Tooltip>
        <Tooltip content={isSelectionMode && selectedKeys.length > 0 ? "删除选中区间摘要" : "删除全部区间摘要"}>
          <IconButton
            variant="ghost"
            size="2"
            color="red"
            onClick={() => setDeleteDialogOpen(true)}
            disabled={deleteMutation.isPending || items.length === 0}
          >
            <Trash2 size={16} />
          </IconButton>
        </Tooltip>
      </Flex>

      {isListLoading ? (
        <LongTermSummarySkeletonList />
      ) : items.length === 0 ? (
        <Flex align="center" justify="center" py="8">
          <Text size="2" color="gray">
            {searchQuery ? "当前页没有匹配的区间摘要。" : emptyText}
          </Text>
        </Flex>
      ) : (
        <Flex direction="column" gap="2">
          {items.map((item) => {
            const key = `${item.startOrder}-${item.endOrder}`;
            return (
              <LongTermSummaryAccordionItem
                key={key}
                item={item}
                expanded={expandedKeySet.has(key)}
                selected={selectedKeySet.has(key)}
                isSelecting={isSelectionMode}
                onToggleExpand={() => handleToggleExpand(key)}
                onToggleSelect={() => handleToggleSelect(key)}
              />
            );
          })}
        </Flex>
      )}

      {isInitialLoading && !searchQuery ? (
        <SummaryPaginationSkeleton />
      ) : total > 0 && !searchQuery ? (
        <Flex align="center" justify="between" wrap="wrap" gap="3">
          <Text size="2" color="gray">
            第 {pageStart} - {pageEnd} 条，共 {total} 条
          </Text>
          <Flex align="center" gap="2" wrap="wrap">
            <Text size="2" color="gray">
              总页数: {totalPages}
            </Text>
            <IconButton
              aria-label="上一页"
              color="gray"
              disabled={currentPage <= 1 || isFetching}
              size="1"
              variant="ghost"
              onClick={() => setPage((current) => current - 1)}
            >
              <ChevronLeft size={14} />
            </IconButton>
            <Flex align="center" gap="1" aria-label="页码列表">
              {visiblePages.map((visiblePage, index) =>
                visiblePage === "ellipsis" ? (
                  <Text key={`ellipsis-${index}`} size="2" color="gray">
                    ...
                  </Text>
                ) : (
                  <button
                    type="button"
                    key={visiblePage}
                    onClick={() => setPage(visiblePage)}
                    disabled={isFetching || visiblePage === currentPage}
                    className="summary-pagination-page"
                    data-active={visiblePage === currentPage}
                  >
                    {visiblePage}
                  </button>
                )
              )}
            </Flex>
            <IconButton
              aria-label="下一页"
              color="gray"
              disabled={currentPage >= totalPages || isFetching}
              size="1"
              variant="ghost"
              onClick={() => setPage((current) => current + 1)}
            >
              <ChevronRight size={14} />
            </IconButton>
          </Flex>
        </Flex>
      ) : null}

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleConfirmDelete}
        title={isSelectionMode && selectedKeys.length > 0 ? "删除选中的区间摘要" : "删除全部区间摘要"}
        description={
          isSelectionMode && selectedKeys.length > 0
            ? `将删除 ${selectedKeys.length} 个已选区间的摘要内容。`
            : "将删除当前项目下全部区间摘要内容。"
        }
        confirmText="删除"
        confirmColor="red"
        loading={deleteMutation.isPending}
      />
    </Flex>
  );
}
