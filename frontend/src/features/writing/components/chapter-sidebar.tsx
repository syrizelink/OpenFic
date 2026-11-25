import { Box, Button, Dialog, Flex, TextArea } from "@radix-ui/themes";
import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useShallow } from "zustand/react/shallow";

import { ConfirmDialog, toast } from "@/components";
import { fetchChapter } from "@/lib/api-client";
import type { ChapterListItem, VolumeWithChapters } from "@/lib/chapter.types";
import { createToastThrottler } from "@/lib/ui-utils";

import {
  useCreateChapter,
  useUpdateChapter,
  useDeleteChapter,
  useDeleteChapters,
  useReorderChapters,
  useMoveChapterToVolume,
  useMoveChaptersToVolume,
} from "../hooks/use-chapters";
import { useSummaryStatuses } from "../hooks/use-summaries";
import {
  useCreateVolume,
  useDeleteVolume,
  useMoveVolume,
  useUpdateVolume,
  useVolumeTree,
} from "../hooks/use-volumes";
import { useTabsStore } from "../store/use-tabs-store";
import { useWritingStore } from "../store/use-writing-store";
import { ChapterExportDialog } from "./chapter-export-dialog";
import type { ChapterSelectionAction } from "./grouped-volume-list";
import {
  findVolumeIdForChapter,
  getInitialCurrentChapterVolumeIdToExpand,
  type GroupedVolumeListScrollRequest,
} from "./grouped-volume-list-focus";
import { MoveChapterToVolumeDialog } from "./move-chapter-to-volume-dialog";
import { SidebarToolbar } from "./sidebar-toolbar";
import { VolumeList } from "./volume-list";

interface ChapterSidebarProps {
  projectId: string;
  onChapterSelect: (chapterId: string, chapterTitle: string) => void;
  onAddToConversation?: (markup: string) => void;
  isAgentLocked?: boolean;
  compact?: boolean;
  initialCurrentChapterNavigationKey?: string | null;
  onOpenSummary?: () => void;
}

export function ChapterSidebar({
  projectId,
  onChapterSelect,
  onAddToConversation,
  isAgentLocked = false,
  compact = false,
  initialCurrentChapterNavigationKey = null,
  onOpenSummary,
}: ChapterSidebarProps) {
  const { t } = useTranslation();

  const { data, isLoading } = useVolumeTree(projectId);
  const { data: summaryStatuses } = useSummaryStatuses(projectId);
  const createChapterMutation = useCreateChapter(projectId);
  const updateChapterMutation = useUpdateChapter();
  const deleteChapterMutation = useDeleteChapter(projectId);
  const deleteChaptersMutation = useDeleteChapters(projectId);
  const reorderChaptersMutation = useReorderChapters(projectId);
  const moveChapterToVolumeMutation = useMoveChapterToVolume(projectId);
  const moveChaptersToVolumeMutation = useMoveChaptersToVolume(projectId);
  const createVolumeMutation = useCreateVolume(projectId);
  const updateVolumeMutation = useUpdateVolume();
  const deleteVolumeMutation = useDeleteVolume(projectId);
  const moveVolumeMutation = useMoveVolume(projectId);

  const { openTab, tabs } = useTabsStore();
  const MAX_TABS = 10;

  const {
    hasUnsavedDragChanges,
    dragOrderMap,
    exitDragMode,
    currentChapterId,
    setCurrentChapter,
    expandedVolumeIds,
    hasHydratedExpandedVolumeIds,
    hasStoredExpandedVolumeIdsPreference,
    hydrateExpandedVolumeIds,
    setVolumeExpanded,
    toggleVolumeExpanded,
  } = useWritingStore(
    useShallow((state) => ({
      hasUnsavedDragChanges: state.hasUnsavedDragChanges,
      dragOrderMap: state.dragOrderMap,
      exitDragMode: state.exitDragMode,
      currentChapterId: state.currentChapterId,
      setCurrentChapter: state.setCurrentChapter,
      expandedVolumeIds: state.expandedVolumeIds,
      hasHydratedExpandedVolumeIds: state.hasHydratedExpandedVolumeIds,
      hasStoredExpandedVolumeIdsPreference: state.hasStoredExpandedVolumeIdsPreference,
      hydrateExpandedVolumeIds: state.hydrateExpandedVolumeIds,
      setVolumeExpanded: state.setVolumeExpanded,
      toggleVolumeExpanded: state.toggleVolumeExpanded,
    })),
  );

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingChapter, setDeletingChapter] = useState<ChapterListItem | null>(null);
  const [deletingVolume, setDeletingVolume] = useState<VolumeWithChapters | null>(null);
  const [saveOrderDialogOpen, setSaveOrderDialogOpen] = useState(false);
  const [cancelOrderDialogOpen, setCancelOrderDialogOpen] = useState(false);
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [movingChapter, setMovingChapter] = useState<ChapterListItem | null>(null);
  const [batchMovingChapters, setBatchMovingChapters] = useState<ChapterListItem[]>([]);
  const [batchDeletingChapters, setBatchDeletingChapters] = useState<ChapterListItem[]>([]);
  const [isBatchPending, setIsBatchPending] = useState(false);
  const isBatchPendingRef = useRef(false);
  const [renamingVolumeId, setRenamingVolumeId] = useState<string | null>(null);
  const [editingVolume, setEditingVolume] = useState<VolumeWithChapters | null>(null);
  const [editingVolumeDescription, setEditingVolumeDescription] = useState("");
  const [chapterExportOpen, setChapterExportOpen] = useState(false);
  const [exportSelection, setExportSelection] = useState<Set<string> | null>(null);
  const [isSelectMode, setIsSelectMode] = useState(false);
  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<string>>(new Set());
  const selectionAnchorRef = useRef<string | null>(null);
  const [localTitleOverrides, setLocalTitleOverrides] = useState<Record<string, string>>({});
  const [scrollRequest, setScrollRequest] = useState<GroupedVolumeListScrollRequest | null>(null);
  const defaultExpansionAppliedProjectRef = useRef<string | null>(null);
  const scrollRequestSequenceRef = useRef(0);
  const lastHandledInitialCurrentChapterNavigationKeyRef = useRef<string | null>(null);

  const showLockedToast = useMemo(
    () => createToastThrottler(t("writing.agentLockedChapterEdit")),
    [t],
  );

  useEffect(() => {
    void hydrateExpandedVolumeIds();
  }, [hydrateExpandedVolumeIds]);

  const volumes = useMemo(() => {
    const source = data?.volumes ?? [];
    if (Object.keys(localTitleOverrides).length === 0) return source;

    return source.map((volume) => ({
      ...volume,
      chapters: volume.chapters.map((chapter) => {
        const localTitle = localTitleOverrides[chapter.id];
        return localTitle && chapter.title !== localTitle
          ? { ...chapter, title: localTitle }
          : chapter;
      }),
    }));
  }, [data?.volumes, localTitleOverrides]);

  useEffect(() => {
    if (!hasHydratedExpandedVolumeIds || !volumes.length) return;
    if (defaultExpansionAppliedProjectRef.current === projectId) return;
    defaultExpansionAppliedProjectRef.current = projectId;
    if (hasStoredExpandedVolumeIdsPreference) return;
    if (expandedVolumeIds.size > 0) return;
    volumes.forEach((volume) => setVolumeExpanded(volume.id, true));
  }, [
    expandedVolumeIds.size,
    hasHydratedExpandedVolumeIds,
    hasStoredExpandedVolumeIdsPreference,
    projectId,
    setVolumeExpanded,
    volumes,
  ]);

  useEffect(() => {
    if (!hasHydratedExpandedVolumeIds || !initialCurrentChapterNavigationKey) {
      return;
    }

    if (
      lastHandledInitialCurrentChapterNavigationKeyRef.current ===
      initialCurrentChapterNavigationKey
    ) {
      return;
    }

    const volumeId = findVolumeIdForChapter(volumes, currentChapterId);
    if (!volumeId) {
      return;
    }

    lastHandledInitialCurrentChapterNavigationKeyRef.current = initialCurrentChapterNavigationKey;

    const targetVolumeId = getInitialCurrentChapterVolumeIdToExpand({
      initialNavigationKey: initialCurrentChapterNavigationKey,
      volumes,
      expandedVolumeIds,
      currentChapterId,
    });

    if (!targetVolumeId) {
      return;
    }

    setVolumeExpanded(targetVolumeId, true);
  }, [
    currentChapterId,
    expandedVolumeIds,
    hasHydratedExpandedVolumeIds,
    initialCurrentChapterNavigationKey,
    setVolumeExpanded,
    volumes,
  ]);

  const allChapters = useMemo(() => volumes.flatMap((volume) => volume.chapters), [volumes]);
  const selectedChapters = useMemo(
    () => allChapters.filter((chapter) => selectedChapterIds.has(chapter.id)),
    [allChapters, selectedChapterIds],
  );
  const chaptersToMove = useMemo(
    () => (batchMovingChapters.length ? batchMovingChapters : movingChapter ? [movingChapter] : []),
    [batchMovingChapters, movingChapter],
  );

  const handleToggleSelectMode = useCallback(() => {
    setIsSelectMode((previous) => !previous);
    setSelectedChapterIds(new Set());
    selectionAnchorRef.current = null;
  }, []);

  const handleToggleChapter = useCallback(
    (chapterId: string) => {
      if (isBatchPending) return;
      selectionAnchorRef.current = chapterId;
      setSelectedChapterIds((previous) => {
        const next = new Set(previous);
        if (next.has(chapterId)) next.delete(chapterId);
        else next.add(chapterId);
        return next;
      });
    },
    [isBatchPending],
  );

  const handleSelectionAction = useCallback(
    (action: ChapterSelectionAction, chapterId: string) => {
      if (isBatchPending) return;
      const ids = allChapters.map((chapter) => chapter.id);
      const index = ids.indexOf(chapterId);
      if (index < 0) return;
      if (action === "all" && ids.every((id) => selectedChapterIds.has(id))) {
        selectionAnchorRef.current = null;
        setSelectedChapterIds(new Set());
        return;
      }
      const anchorIndex = selectionAnchorRef.current ? ids.indexOf(selectionAnchorRef.current) : -1;
      let affectedIds: string[];
      if (action === "all") affectedIds = ids;
      else if (action === "above") affectedIds = ids.slice(0, index + 1);
      else if (action === "below") affectedIds = ids.slice(index);
      else if (action === "range" && anchorIndex >= 0) {
        affectedIds = ids.slice(Math.min(index, anchorIndex), Math.max(index, anchorIndex) + 1);
      } else affectedIds = [chapterId];

      if (action !== "all" && (action !== "range" || anchorIndex < 0)) {
        selectionAnchorRef.current = chapterId;
      }
      setSelectedChapterIds((previous) => {
        const next = new Set(previous);
        for (const id of affectedIds) {
          if (action === "deselect") next.delete(id);
          else next.add(id);
        }
        return next;
      });
    },
    [allChapters, isBatchPending, selectedChapterIds],
  );

  const handleOpenBatchDelete = useCallback(() => {
    if (isAgentLocked) return showLockedToast();
    setBatchDeletingChapters(selectedChapters);
  }, [isAgentLocked, selectedChapters, showLockedToast]);

  const handleOpenBatchMove = useCallback(() => {
    if (isAgentLocked) return showLockedToast();
    setBatchMovingChapters(selectedChapters);
    setMovingChapter(null);
    setMoveDialogOpen(true);
  }, [isAgentLocked, selectedChapters, showLockedToast]);

  const handleOpenBatchExport = useCallback(() => {
    setExportSelection(new Set(selectedChapters.map((chapter) => chapter.id)));
    setChapterExportOpen(true);
  }, [selectedChapters]);

  const handleBatchDelete = useCallback(async () => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }
    isBatchPendingRef.current = true;
    setIsBatchPending(true);
    try {
      await deleteChaptersMutation.mutateAsync(batchDeletingChapters.map((chapter) => chapter.id));
      setSelectedChapterIds(new Set());
      setBatchDeletingChapters([]);
      toast.success(t("writing.batchDeleteSuccess"));
    } catch {
      toast.error(t("writing.batchDeleteFailed"));
    } finally {
      isBatchPendingRef.current = false;
      setIsBatchPending(false);
    }
  }, [batchDeletingChapters, deleteChaptersMutation, isAgentLocked, showLockedToast, t]);

  const createScrollRequestKey = useCallback((prefix: string, id: string) => {
    scrollRequestSequenceRef.current += 1;
    return `${prefix}:${id}:${scrollRequestSequenceRef.current}`;
  }, []);

  const summaryStatusMap = useMemo(
    () => Object.fromEntries((summaryStatuses ?? []).map((item) => [item.chapterId, item])),
    [summaryStatuses],
  );

  const createChapterInVolume = useCallback(
    async (volumeId: string) => {
      if (isAgentLocked) {
        showLockedToast();
        return null;
      }

      const newChapter = await createChapterMutation.mutateAsync({
        volumeId,
        title: t("writing.untitledChapter"),
      });
      setVolumeExpanded(volumeId, true);
      setScrollRequest({
        key: createScrollRequestKey("chapter", newChapter.id),
        type: "chapter",
        chapterId: newChapter.id,
      });
      setCurrentChapter(newChapter.id);
      onChapterSelect(newChapter.id, newChapter.title);
      return newChapter;
    },
    [
      createChapterMutation,
      isAgentLocked,
      onChapterSelect,
      setCurrentChapter,
      setVolumeExpanded,
      createScrollRequestKey,
      showLockedToast,
      t,
    ],
  );

  const handleCreateChapter = useCallback(async () => {
    const targetVolume = volumes[volumes.length - 1];
    if (targetVolume) {
      await createChapterInVolume(targetVolume.id);
      return;
    }

    const volume = await createVolumeMutation.mutateAsync({
      title: t("writing.firstVolumeDefaultTitle"),
    });
    await createChapterInVolume(volume.id);
  }, [createChapterInVolume, createVolumeMutation, t, volumes]);

  const handleCreateVolume = useCallback(async () => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }
    const volume = await createVolumeMutation.mutateAsync({
      title: t("volume.untitled"),
    });
    setVolumeExpanded(volume.id, true);
    setScrollRequest({
      key: createScrollRequestKey("volume", volume.id),
      type: "volume",
      volumeId: volume.id,
    });
  }, [
    createScrollRequestKey,
    createVolumeMutation,
    isAgentLocked,
    setVolumeExpanded,
    showLockedToast,
    t,
  ]);

  const handleChapterSelect = useCallback(
    (chapterId: string) => {
      const chapter = allChapters.find((item) => item.id === chapterId);
      setCurrentChapter(chapterId);
      onChapterSelect(chapterId, chapter?.title ?? "");
    },
    [allChapters, onChapterSelect, setCurrentChapter],
  );

  const handleOpenInNewTab = useCallback(
    (chapterId: string, title: string) => {
      if (tabs.length >= MAX_TABS) {
        // openTab 内部会处理满的情况
      }
      openTab(chapterId, title);
    },
    [openTab, tabs.length],
  );

  const handleDuplicate = useCallback(
    async (chapterId: string, title: string) => {
      if (isAgentLocked) {
        showLockedToast();
        return;
      }

      try {
        const originalChapter = await fetchChapter(chapterId);
        const newChapter = await createChapterMutation.mutateAsync({
          volumeId: originalChapter.volumeId,
          title: `${title}-副本`,
          content: originalChapter.content,
          wordCount: originalChapter.wordCount,
        });
        setCurrentChapter(newChapter.id);
        onChapterSelect(newChapter.id, newChapter.title);
      } catch {
        // 错误处理由 mutation 处理
      }
    },
    [createChapterMutation, isAgentLocked, onChapterSelect, setCurrentChapter, showLockedToast],
  );

  const handleRenameChapter = useCallback(
    async (chapterId: string, newTitle: string) => {
      if (isAgentLocked) {
        showLockedToast();
        return;
      }

      setLocalTitleOverrides((prev) => ({ ...prev, [chapterId]: newTitle }));

      try {
        await updateChapterMutation.mutateAsync({
          chapterId,
          data: { title: newTitle },
        });
      } catch {
        setLocalTitleOverrides((prev) => {
          const next = { ...prev };
          delete next[chapterId];
          return next;
        });
      }
    },
    [isAgentLocked, showLockedToast, updateChapterMutation],
  );

  const handleOpenDeleteChapter = useCallback(
    (chapter: ChapterListItem) => {
      if (isAgentLocked) {
        showLockedToast();
        return;
      }

      setDeletingChapter(chapter);
      setDeletingVolume(null);
      setDeleteDialogOpen(true);
    },
    [isAgentLocked, showLockedToast],
  );

  const handleOpenDeleteVolume = useCallback(
    (volume: VolumeWithChapters) => {
      if (isAgentLocked) {
        showLockedToast();
        return;
      }
      setDeletingVolume(volume);
      setDeletingChapter(null);
      setDeleteDialogOpen(true);
    },
    [isAgentLocked, showLockedToast],
  );

  const handleDeleteDialogChange = useCallback((open: boolean) => {
    setDeleteDialogOpen(open);
    if (!open) {
      setDeletingChapter(null);
      setDeletingVolume(null);
    }
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (deletingChapter) {
      try {
        await deleteChapterMutation.mutateAsync(deletingChapter.id);
        toast.success(t("writing.deleteChapterSuccess"));
        handleDeleteDialogChange(false);
      } catch {
        toast.error(t("writing.deleteChapterFailed"));
      }
      return;
    }

    if (deletingVolume) {
      try {
        await deleteVolumeMutation.mutateAsync({
          volumeId: deletingVolume.id,
          cascade: deletingVolume.chapterCount > 0,
        });
        toast.success(t("writing.deleteVolumeSuccess"));
        handleDeleteDialogChange(false);
      } catch {
        toast.error(t("writing.deleteVolumeFailed"));
      }
    }
  }, [
    deleteChapterMutation,
    deleteVolumeMutation,
    deletingChapter,
    deletingVolume,
    handleDeleteDialogChange,
    t,
  ]);

  const handleSaveOrder = useCallback(() => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }

    if (hasUnsavedDragChanges) {
      setSaveOrderDialogOpen(true);
    }
  }, [hasUnsavedDragChanges, isAgentLocked, showLockedToast]);

  const handleConfirmSaveOrder = useCallback(async () => {
    try {
      for (const volume of volumes) {
        const hasChanges = volume.chapters.some(
          (chapter) =>
            dragOrderMap[chapter.id] !== undefined && dragOrderMap[chapter.id] !== chapter.order,
        );
        if (!hasChanges) continue;

        const sortedChapterIds = [...volume.chapters]
          .sort((a, b) => (dragOrderMap[a.id] ?? a.order) - (dragOrderMap[b.id] ?? b.order))
          .map((c) => c.id);

        await reorderChaptersMutation.mutateAsync({
          volumeId: volume.id,
          chapterIds: sortedChapterIds,
        });
      }
      exitDragMode();
      setSaveOrderDialogOpen(false);
    } catch {
      // 错误处理由 mutation 处理
    }
  }, [dragOrderMap, exitDragMode, reorderChaptersMutation, volumes]);

  const handleCancelOrder = useCallback(() => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }

    if (hasUnsavedDragChanges) {
      setCancelOrderDialogOpen(true);
    } else {
      exitDragMode();
    }
  }, [exitDragMode, hasUnsavedDragChanges, isAgentLocked, showLockedToast]);

  const handleConfirmCancelOrder = useCallback(() => {
    exitDragMode();
    setCancelOrderDialogOpen(false);
  }, [exitDragMode]);

  const handleRenameVolume = useCallback(
    async (volumeId: string, title: string) => {
      if (isAgentLocked) {
        showLockedToast();
        return;
      }
      setRenamingVolumeId(null);
      await updateVolumeMutation.mutateAsync({
        volumeId,
        data: { title },
      });
    },
    [isAgentLocked, showLockedToast, updateVolumeMutation],
  );

  const handleOpenDescriptionEditor = useCallback((volume: VolumeWithChapters) => {
    setEditingVolume(volume);
    setEditingVolumeDescription(volume.description ?? "");
  }, []);

  const handleSaveDescription = useCallback(async () => {
    if (!editingVolume) return;
    await updateVolumeMutation.mutateAsync({
      volumeId: editingVolume.id,
      data: { description: editingVolumeDescription.trim() || null },
    });
    setEditingVolume(null);
    setEditingVolumeDescription("");
  }, [editingVolume, editingVolumeDescription, updateVolumeMutation]);

  const handleMoveVolume = useCallback(
    async (volume: VolumeWithChapters, direction: -1 | 1) => {
      if (isAgentLocked) {
        showLockedToast();
        return;
      }
      await moveVolumeMutation.mutateAsync({
        volumeId: volume.id,
        newOrder: volume.order + direction,
      });
    },
    [isAgentLocked, moveVolumeMutation, showLockedToast],
  );

  const handleOpenMoveChapter = useCallback(
    (chapter: ChapterListItem) => {
      if (isAgentLocked) {
        showLockedToast();
        return;
      }
      setMovingChapter(chapter);
      setMoveDialogOpen(true);
    },
    [isAgentLocked, showLockedToast],
  );

  const handleConfirmMoveChapter = useCallback(
    async (volumeId: string) => {
      if (batchMovingChapters.length) {
        if (isAgentLocked) {
          showLockedToast();
          return;
        }
        setIsBatchPending(true);
        try {
          await moveChaptersToVolumeMutation.mutateAsync({
            chapterIds: batchMovingChapters.map((chapter) => chapter.id),
            volumeId,
          });
          setSelectedChapterIds(new Set());
          setVolumeExpanded(volumeId, true);
          setMoveDialogOpen(false);
          setBatchMovingChapters([]);
          toast.success(t("writing.batchMoveSuccess"));
        } catch {
          toast.error(t("writing.batchMoveFailed"));
        } finally {
          setIsBatchPending(false);
        }
        return;
      }
      if (!movingChapter) return;
      await moveChapterToVolumeMutation.mutateAsync({
        chapterId: movingChapter.id,
        volumeId,
      });
      setVolumeExpanded(volumeId, true);
      setMoveDialogOpen(false);
      setMovingChapter(null);
    },
    [
      batchMovingChapters,
      isAgentLocked,
      moveChapterToVolumeMutation,
      moveChaptersToVolumeMutation,
      movingChapter,
      setVolumeExpanded,
      showLockedToast,
      t,
    ],
  );

  return (
    <Box
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "var(--color-background)",
      }}
    >
      <SidebarToolbar
        projectId={projectId}
        chapters={allChapters}
        onChapterSelect={handleChapterSelect}
        onCreateChapter={handleCreateChapter}
        onCreateVolume={handleCreateVolume}
        onOpenSummary={onOpenSummary}
        onExport={() => {
          setExportSelection(null);
          setChapterExportOpen(true);
        }}
        onSaveOrder={handleSaveOrder}
        onCancelOrder={handleCancelOrder}
        isSelectMode={isSelectMode}
        onToggleSelectMode={handleToggleSelectMode}
        selectedCount={selectedChapters.length}
        isBatchPending={isBatchPending}
        onBatchDelete={handleOpenBatchDelete}
        onBatchMove={handleOpenBatchMove}
        onBatchExport={handleOpenBatchExport}
        isSavingOrder={reorderChaptersMutation.isPending}
        isAgentLocked={isAgentLocked}
        onLockedAction={showLockedToast}
      />

      <VolumeList
        projectId={projectId}
        volumes={volumes}
        isLoading={isLoading}
        scrollRequest={scrollRequest}
        expandedVolumeIds={expandedVolumeIds}
        renamingVolumeId={renamingVolumeId}
        isAgentLocked={isAgentLocked}
        compact={compact}
        summaryStatusMap={summaryStatusMap}
        onOpenSummary={onOpenSummary}
        initialCurrentChapterNavigationKey={initialCurrentChapterNavigationKey}
        onToggleVolume={toggleVolumeExpanded}
        onStartRenameVolume={setRenamingVolumeId}
        onRenameVolume={handleRenameVolume}
        onCancelRenameVolume={() => setRenamingVolumeId(null)}
        onEditVolumeDescription={handleOpenDescriptionEditor}
        onCreateChapterInVolume={(volumeId) => void createChapterInVolume(volumeId)}
        onMoveVolumeUp={(volume) => void handleMoveVolume(volume, -1)}
        onMoveVolumeDown={(volume) => void handleMoveVolume(volume, 1)}
        onDeleteVolume={handleOpenDeleteVolume}
        onChapterSelect={handleChapterSelect}
        isSelectMode={isSelectMode}
        selectedChapterIds={selectedChapterIds}
        onToggleChapter={handleToggleChapter}
        onSelectionAction={handleSelectionAction}
        onBatchDelete={handleOpenBatchDelete}
        onBatchMove={handleOpenBatchMove}
        onBatchExport={handleOpenBatchExport}
        isBatchPending={isBatchPending}
        onOpenInNewTab={handleOpenInNewTab}
        onDuplicate={handleDuplicate}
        onRenameChapter={handleRenameChapter}
        onMoveChapterToVolume={handleOpenMoveChapter}
        onDeleteChapter={handleOpenDeleteChapter}
        onAddToConversation={onAddToConversation}
        onLockedAction={showLockedToast}
      />

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={handleDeleteDialogChange}
        title={deletingVolume ? t("volume.menu.delete") : t("chapterMenu.delete")}
        description={
          deletingVolume
            ? deletingVolume.chapterCount > 0
              ? t("volume.deleteCascadeConfirm")
              : t("volume.deleteConfirm")
            : (deletingChapter?.title ?? "")
        }
        onConfirm={handleConfirmDelete}
        loading={deleteChapterMutation.isPending || deleteVolumeMutation.isPending}
      />

      <ConfirmDialog
        open={batchDeletingChapters.length > 0}
        onOpenChange={(open) => {
          if (!open && !isBatchPendingRef.current) setBatchDeletingChapters([]);
        }}
        title={t("writing.batchDelete")}
        description={t("writing.batchDeleteConfirm", { count: batchDeletingChapters.length })}
        onConfirm={handleBatchDelete}
        loading={isBatchPending}
      />

      <ConfirmDialog
        open={saveOrderDialogOpen}
        onOpenChange={setSaveOrderDialogOpen}
        title={t("writing.saveOrder")}
        description={t("writing.saveOrderConfirm")}
        onConfirm={handleConfirmSaveOrder}
      />

      <ConfirmDialog
        open={cancelOrderDialogOpen}
        onOpenChange={setCancelOrderDialogOpen}
        title={t("writing.cancelOrder")}
        description={t("writing.cancelOrderConfirm")}
        onConfirm={handleConfirmCancelOrder}
      />

      <MoveChapterToVolumeDialog
        open={moveDialogOpen}
        chapters={chaptersToMove}
        volumes={volumes}
        onOpenChange={(open) => {
          setMoveDialogOpen(open);
          if (!open) setMovingChapter(null);
          if (!open) setBatchMovingChapters([]);
        }}
        onConfirm={handleConfirmMoveChapter}
        loading={isBatchPending || moveChapterToVolumeMutation.isPending}
      />

      <ChapterExportDialog
        open={chapterExportOpen}
        onOpenChange={setChapterExportOpen}
        projectId={projectId}
        volumes={volumes}
        initialSelectedChapterIds={exportSelection}
      />

      <Dialog.Root
        open={Boolean(editingVolume)}
        onOpenChange={(open) => {
          if (!open) {
            setEditingVolume(null);
            setEditingVolumeDescription("");
          }
        }}
      >
        <Dialog.Content maxWidth="420px">
          <Dialog.Title>{t("volume.menu.editDescription")}</Dialog.Title>
          <Dialog.Description
            size="2"
            color="gray"
          >
            {editingVolume?.title ?? t("volume.untitled")}
          </Dialog.Description>
          <TextArea
            mt="4"
            value={editingVolumeDescription}
            onChange={(event) => setEditingVolumeDescription(event.target.value)}
            resize="vertical"
            style={{ minHeight: 120 }}
          />
          <Flex
            justify="end"
            gap="3"
            mt="4"
          >
            <Dialog.Close>
              <Button
                variant="soft"
                color="gray"
              >
                {t("common.cancel")}
              </Button>
            </Dialog.Close>
            <Button
              loading={updateVolumeMutation.isPending}
              onClick={() => void handleSaveDescription()}
            >
              {t("common.confirm")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  );
}
