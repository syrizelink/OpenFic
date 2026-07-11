import {
  Badge,
  Box,
  Checkbox,
  Flex,
  IconButton,
  Skeleton,
  Text,
  TextField,
  Tooltip,
} from "@radix-ui/themes";
import axios from "axios";
import { ChevronDown, ChevronLeft, ChevronRight, ListChecks, Search, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { memo, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import "./summary-panel.css";

import { ConfirmDialog, SimpleSelect, toast } from "@/components";
import type { ChapterSummaryListItem } from "@/lib/api-client";
import i18n from "@/i18n";

import { useChapterSummaryListPage, useDeleteChapterSummaries } from "../hooks/use-summaries";
import { useVolumeTree } from "../hooks/use-volumes";

const CHAPTER_SUMMARY_PAGE_SIZE = 20;
const EMPTY_CHAPTER_SUMMARIES: ChapterSummaryListItem[] = [];

interface ApiErrorPayload {
  detail?: unknown;
  message?: unknown;
}

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

function getVisiblePages(currentPage: number, totalPages: number): Array<number | "ellipsis"> {
  if (totalPages <= 6) return Array.from({ length: totalPages }, (_, index) => index + 1);
  if (currentPage <= 3) return [1, 2, 3, "ellipsis", totalPages - 1, totalPages];
  if (currentPage >= totalPages - 2)
    return [1, 2, "ellipsis", totalPages - 2, totalPages - 1, totalPages];
  return [1, currentPage - 1, currentPage, "ellipsis", currentPage + 1, totalPages];
}

function ChapterSummarySkeletonList() {
  return (
    <Flex
      direction="column"
      gap="2"
    >
      {Array.from({ length: CHAPTER_SUMMARY_PAGE_SIZE }, (_, index) => (
        <Box
          key={index}
          className="summary-card"
        >
          <Flex
            align="center"
            gap="3"
            px="3"
            py="2"
            className="summary-row"
          >
            <Skeleton
              height="16px"
              width="16px"
              style={{ borderRadius: 999 }}
            />
            <Skeleton
              height="16px"
              width={`${40 + (index % 3) * 8}%`}
              style={{ maxWidth: 240 }}
            />
            <Flex
              gap="2"
              className="summary-row-fill"
            >
              <Skeleton
                height="20px"
                width="56px"
                style={{ borderRadius: 999 }}
              />
              <Skeleton
                height="20px"
                width="68px"
                style={{ borderRadius: 999 }}
              />
              {index % 2 === 0 && (
                <Skeleton
                  height="20px"
                  width="52px"
                  style={{ borderRadius: 999 }}
                />
              )}
            </Flex>
            <Skeleton
              height="20px"
              width="56px"
              style={{ borderRadius: 999 }}
            />
          </Flex>
        </Box>
      ))}
    </Flex>
  );
}

interface ChapterSummaryAccordionItemProps {
  item: ChapterSummaryListItem;
  expanded: boolean;
  selected: boolean;
  isSelecting: boolean;
  onToggleExpand: () => void;
  onToggleSelect: () => void;
}

function SummaryPaginationSkeleton() {
  return (
    <Flex
      align="center"
      justify="between"
      wrap="wrap"
      gap="3"
    >
      <Skeleton
        height="16px"
        width="160px"
      />
      <Flex
        align="center"
        gap="2"
        wrap="wrap"
      >
        <Skeleton
          height="16px"
          width="72px"
        />
        <Skeleton
          height="28px"
          width="52px"
          style={{ borderRadius: 999 }}
        />
        <Flex
          align="center"
          gap="1"
        >
          <Skeleton
            height="28px"
            width="28px"
            style={{ borderRadius: 999 }}
          />
          <Skeleton
            height="28px"
            width="28px"
            style={{ borderRadius: 999 }}
          />
          <Skeleton
            height="28px"
            width="28px"
            style={{ borderRadius: 999 }}
          />
          <Skeleton
            height="28px"
            width="28px"
            style={{ borderRadius: 999 }}
          />
        </Flex>
        <Skeleton
          height="28px"
          width="52px"
          style={{ borderRadius: 999 }}
        />
      </Flex>
    </Flex>
  );
}

const ChapterSummaryAccordionItem = memo(function ChapterSummaryAccordionItem({
  item,
  expanded,
  selected,
  isSelecting,
  onToggleExpand,
  onToggleSelect,
}: ChapterSummaryAccordionItemProps) {
  const { t } = useTranslation();
  const tags = [...item.characters, ...item.locations].slice(0, 8);
  const canExpand = item.status !== "not_generated";

  return (
    <Box
      className="summary-card"
      data-selected={selected ? "true" : "false"}
    >
      <Flex
        align="center"
        gap="3"
        px="3"
        py="2"
        className="summary-row"
      >
        {isSelecting && (
          <Checkbox
            checked={selected}
            onCheckedChange={onToggleSelect}
          />
        )}
        <button
          type="button"
          onClick={canExpand ? onToggleExpand : undefined}
          disabled={!canExpand}
          className="summary-expand-button"
          data-expandable={canExpand ? "true" : "false"}
          aria-label={expanded ? t("summary.collapseAria") : t("summary.expandAria")}
        >
          <ChevronDown
            size={14}
            className="summary-expand-icon"
            data-expanded={expanded ? "true" : "false"}
          />
        </button>
        <Flex
          direction="column"
          gap="1"
          className="summary-chapter-meta"
        >
          <Text
            size="2"
            className="summary-chapter-title"
          >
            {item.volumeTitle && (
              <span className="summary-volume-meta">
                {item.volumeTitle} | {item.chapterOrder}
              </span>
            )}
            {!item.volumeTitle && `${item.chapterOrder}. `}
            {item.chapterTitle}
          </Text>
          {tags.length > 0 && (
            <Flex
              gap="2"
              wrap="wrap"
              className="summary-chapter-tags"
            >
              {tags.map((tag) => (
                <Badge
                  key={`${item.chapterId}-${tag}`}
                  variant="soft"
                  color="gray"
                >
                  {tag}
                </Badge>
              ))}
            </Flex>
          )}
        </Flex>
        <Box className="summary-row-fixed">
          <SummaryStatusBadge
            status={item.status}
            isStale={item.isStale}
          />
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
            <Box
              className="summary-accordion-content__inner"
              px="3"
            >
              <Flex
                direction="column"
                gap="2"
              >
                {(item.startTime || item.endTime) && (
                  <Text
                    size="1"
                    color="gray"
                  >
                    {item.startTime || t("summary.unknownTime")} - {item.endTime || t("summary.unknownTime")}
                  </Text>
                )}
                <Text
                  size="2"
                  className="summary-content-text"
                >
                  {item.summary || t("summary.noSummaryContent")}
                </Text>
                {item.errorMessage && (
                  <Text
                    size="1"
                    color="red"
                  >
                    {t(`summary.maintenance.errorMessages.${item.errorMessage}`, { defaultValue: item.errorMessage })}
                  </Text>
                )}
              </Flex>
            </Box>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </Box>
  );
}, areChapterSummaryItemPropsEqual);

function areChapterSummaryItemPropsEqual(
  previous: Readonly<ChapterSummaryAccordionItemProps>,
  next: Readonly<ChapterSummaryAccordionItemProps>,
) {
  return (
    previous.item === next.item &&
    previous.expanded === next.expanded &&
    previous.selected === next.selected &&
    previous.isSelecting === next.isSelecting
  );
}

interface ChapterSummaryListViewProps {
  projectId: string;
  open: boolean;
}

export function ChapterSummaryListView({ projectId, open }: ChapterSummaryListViewProps) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [volumeId, setVolumeId] = useState<string | null>(null);
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedChapterIds, setSelectedChapterIds] = useState<string[]>([]);
  const [expandedChapterIds, setExpandedChapterIds] = useState<string[]>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(true);
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const searchQueryParam = deferredSearchQuery.trim();

  const { data: volumeTree } = useVolumeTree(projectId);
  const volumeOptions = useMemo(() => {
    const volumes = volumeTree?.volumes ?? [];
    return [
      { value: "all", label: t("summary.allVolumes") },
      ...volumes.map((v) => ({
        value: v.id,
        label: v.title || t("summary.untitledVolume"),
      })),
    ];
  }, [volumeTree?.volumes, t]);

  const {
    data: chapterSummaryList,
    isLoading,
    isFetching,
    refetch,
  } = useChapterSummaryListPage(projectId, page, volumeId, searchQueryParam);
  const deleteMutation = useDeleteChapterSummaries(projectId);
  const requestPage = page;
  const isInitialLoading = isLoading && !chapterSummaryList;
  const isPageSwitchLoading =
    isFetching && (chapterSummaryList?.page ?? requestPage) !== requestPage;
  const isListLoading = isRefreshing || isInitialLoading || isPageSwitchLoading;

  useEffect(() => {
    if (!open) return;
    setIsRefreshing(true);
    void refetch().finally(() => setIsRefreshing(false));
  }, [open, refetch]);

  const items = chapterSummaryList?.items ?? EMPTY_CHAPTER_SUMMARIES;

  useEffect(() => {
    setPage(1);
  }, [searchQueryParam]);

  const visibleChapterIds = useMemo(() => new Set(items.map((item) => item.chapterId)), [items]);
  const selectedIds = useMemo(
    () => selectedChapterIds.filter((chapterId) => visibleChapterIds.has(chapterId)),
    [selectedChapterIds, visibleChapterIds],
  );
  const expandedIds = useMemo(
    () => expandedChapterIds.filter((chapterId) => visibleChapterIds.has(chapterId)),
    [expandedChapterIds, visibleChapterIds],
  );
  const selectedIdSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const expandedIdSet = useMemo(() => new Set(expandedIds), [expandedIds]);
  const total = chapterSummaryList?.total ?? 0;
  const pageSize = chapterSummaryList?.pageSize ?? CHAPTER_SUMMARY_PAGE_SIZE;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(requestPage, totalPages);
  const visiblePages = useMemo(
    () => getVisiblePages(currentPage, totalPages),
    [currentPage, totalPages],
  );
  const pageStart = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const pageEnd = total === 0 ? 0 : Math.min(currentPage * pageSize, total);

  const handleToggleSelectionMode = () => {
    setIsSelectionMode((value) => {
      if (value) setSelectedChapterIds([]);
      return !value;
    });
  };

  const handleToggleSelect = (chapterId: string) => {
    setSelectedChapterIds((current) =>
      current.includes(chapterId)
        ? current.filter((item) => item !== chapterId)
        : [...current, chapterId],
    );
  };

  const handleToggleExpand = (chapterId: string) => {
    setExpandedChapterIds((current) =>
      current.includes(chapterId)
        ? current.filter((item) => item !== chapterId)
        : [...current, chapterId],
    );
  };

  const handleConfirmDelete = async () => {
    const targetIds = isSelectionMode && selectedIds.length > 0 ? selectedIds : [];
    try {
      const shouldGoToPreviousPage = items.length === 1 && currentPage > 1;
      await deleteMutation.mutateAsync(targetIds);
      setDeleteDialogOpen(false);
      setSelectedChapterIds([]);
      setExpandedChapterIds([]);
      setIsSelectionMode(false);
      if (shouldGoToPreviousPage) {
        setPage((current) => current - 1);
      }
      toast.success(
        targetIds.length > 0
          ? t("summary.deleteSelectedChapterSuccess")
          : t("summary.deleteAllChapterSuccess"),
      );
    } catch (error) {
      toast.error(t("summary.deleteChapterFailed", { reason: getSummaryErrorMessage(error) }));
    }
  };

  const handleVolumeChange = (value: string) => {
    setVolumeId(value === "all" ? null : value);
    setPage(1);
  };

  return (
    <Flex
      direction="column"
      gap="3"
    >
      <Flex
        align="center"
        gap="2"
      >
        <SimpleSelect
          value={volumeId ?? "all"}
          options={volumeOptions}
          onChange={handleVolumeChange}
          size="2"
          triggerClassName="summary-volume-select"
        />
        <TextField.Root
          placeholder={t("summary.searchChapterPlaceholder")}
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          size="2"
          className="summary-search-input"
        >
          <TextField.Slot>
            <Search size={16} />
          </TextField.Slot>
        </TextField.Root>
        <Tooltip
          content={isSelectionMode ? t("summary.cancelSelectMode") : t("summary.selectMode")}
        >
          <IconButton
            variant={isSelectionMode ? "soft" : "ghost"}
            size="2"
            onClick={handleToggleSelectionMode}
          >
            <ListChecks size={16} />
          </IconButton>
        </Tooltip>
        <Tooltip
          content={
            isSelectionMode && selectedIds.length > 0
              ? t("summary.deleteSelectedChapters")
              : t("summary.deleteAllChapters")
          }
        >
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
        <ChapterSummarySkeletonList />
      ) : items.length === 0 ? (
        <Flex
          align="center"
          justify="center"
          py="8"
        >
          <Text
            size="2"
            color="gray"
          >
            {searchQuery ? t("summary.emptyChapterPage") : t("summary.emptyChapters")}
          </Text>
        </Flex>
      ) : (
        <Flex
          direction="column"
          gap="2"
        >
          {items.map((item) => (
            <ChapterSummaryAccordionItem
              key={item.chapterId}
              item={item}
              expanded={expandedIdSet.has(item.chapterId)}
              selected={selectedIdSet.has(item.chapterId)}
              isSelecting={isSelectionMode}
              onToggleExpand={() => handleToggleExpand(item.chapterId)}
              onToggleSelect={() => handleToggleSelect(item.chapterId)}
            />
          ))}
        </Flex>
      )}

      {isInitialLoading ? (
        <SummaryPaginationSkeleton />
      ) : total > 0 ? (
        <Flex
          align="center"
          justify="between"
          wrap="wrap"
          gap="3"
        >
          <Text
            size="2"
            color="gray"
          >
            {t("summary.range", { start: pageStart, end: pageEnd, total })}
          </Text>
          <Flex
            align="center"
            gap="2"
            wrap="wrap"
          >
            <Text
              size="2"
              color="gray"
            >
              {t("summary.totalPages", { total: totalPages })}
            </Text>
            <IconButton
              aria-label={t("summary.prevPage")}
              color="gray"
              disabled={currentPage <= 1 || isFetching}
              size="1"
              variant="ghost"
              onClick={() => setPage((current) => current - 1)}
            >
              <ChevronLeft size={14} />
            </IconButton>
            <Flex
              align="center"
              gap="1"
              aria-label={t("summary.pageList")}
            >
              {visiblePages.map((visiblePage, index) =>
                visiblePage === "ellipsis" ? (
                  <Text
                    key={`ellipsis-${index}`}
                    size="2"
                    color="gray"
                  >
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
                ),
              )}
            </Flex>
            <IconButton
              aria-label={t("summary.nextPage")}
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
        title={
          isSelectionMode && selectedIds.length > 0
            ? t("summary.deleteDialog.deleteSelectedChaptersTitle")
            : t("summary.deleteDialog.deleteAllChaptersTitle")
        }
        description={
          isSelectionMode && selectedIds.length > 0
            ? t("summary.deleteDialog.deleteSelectedChaptersDescription", {
                count: selectedIds.length,
              })
            : t("summary.deleteDialog.deleteAllChaptersDescription")
        }
        confirmText={t("common.delete")}
        confirmColor="red"
        loading={deleteMutation.isPending}
      />
    </Flex>
  );
}
