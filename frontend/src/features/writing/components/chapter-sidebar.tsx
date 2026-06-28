import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { Box, Button, Dialog, Flex, TextArea } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { useShallow } from "zustand/react/shallow";

import { SidebarToolbar } from "./sidebar-toolbar";
import { VolumeList } from "./volume-list";
import { MoveChapterToVolumeDialog } from "./move-chapter-to-volume-dialog";
import {
  findVolumeIdForChapter,
  getInitialCurrentChapterVolumeIdToExpand,
  type GroupedVolumeListScrollRequest,
} from "./grouped-volume-list-focus";
import {
  useCreateChapter,
  useUpdateChapter,
  useDeleteChapter,
  useReorderChapters,
  useMoveChapterToVolume,
} from "../hooks/use-chapters";
import {
  useCreateVolume,
  useDeleteVolume,
  useMoveVolume,
  useUpdateVolume,
  useVolumeTree,
} from "../hooks/use-volumes";
import { useSummaryStatuses } from "../hooks/use-summaries";
import { useWritingStore } from "../store/use-writing-store";
import { useTabsStore } from "../store/use-tabs-store";
import { ConfirmDialog, toast } from "@/components";
import { fetchChapter } from "@/lib/api-client";
import { createToastThrottler } from "@/lib/ui-utils";
import type { ChapterListItem, VolumeWithChapters } from "@/lib/chapter.types";

interface ChapterSidebarProps {
  projectId: string;
  onChapterSelect: (chapterId: string, chapterTitle: string) => void;
  onAddToConversation?: (markup: string) => void;
  isAgentLocked?: boolean;
  compact?: boolean;
  initialCurrentChapterNavigationKey?: string | null;
}

export function ChapterSidebar({
  projectId,
  onChapterSelect,
  onAddToConversation,
  isAgentLocked = false,
  compact = false,
  initialCurrentChapterNavigationKey = null,
}: ChapterSidebarProps) {
  const { t } = useTranslation();

  const { data, isLoading } = useVolumeTree(projectId);
  const { data: summaryStatuses } = useSummaryStatuses(projectId);
  const createChapterMutation = useCreateChapter(projectId);
  const updateChapterMutation = useUpdateChapter();
  const deleteChapterMutation = useDeleteChapter(projectId);
  const reorderChaptersMutation = useReorderChapters(projectId);
  const moveChapterToVolumeMutation = useMoveChapterToVolume(projectId);
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
    }))
  );

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingChapter, setDeletingChapter] = useState<ChapterListItem | null>(null);
  const [deletingVolume, setDeletingVolume] = useState<VolumeWithChapters | null>(null);
  const [saveOrderDialogOpen, setSaveOrderDialogOpen] = useState(false);
  const [cancelOrderDialogOpen, setCancelOrderDialogOpen] = useState(false);
  const [moveDialogOpen, setMoveDialogOpen] = useState(false);
  const [movingChapter, setMovingChapter] = useState<ChapterListItem | null>(null);
  const [renamingVolumeId, setRenamingVolumeId] = useState<string | null>(null);
  const [editingVolume, setEditingVolume] = useState<VolumeWithChapters | null>(null);
  const [editingVolumeDescription, setEditingVolumeDescription] = useState("");
  const [localTitleOverrides, setLocalTitleOverrides] = useState<Record<string, string>>({});
  const [scrollRequest, setScrollRequest] = useState<GroupedVolumeListScrollRequest | null>(null);
  const defaultExpansionAppliedProjectRef = useRef<string | null>(null);
  const scrollRequestSequenceRef = useRef(0);
  const lastHandledInitialCurrentChapterNavigationKeyRef = useRef<string | null>(null);

  const showLockedToast = useMemo(
    () => createToastThrottler("Agent 运行中，章节暂不可修改"),
    []
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

    lastHandledInitialCurrentChapterNavigationKeyRef.current =
      initialCurrentChapterNavigationKey;

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

  const allChapters = useMemo(
    () => volumes.flatMap((volume) => volume.chapters),
    [volumes]
  );

  const createScrollRequestKey = useCallback((prefix: string, id: string) => {
    scrollRequestSequenceRef.current += 1;
    return `${prefix}:${id}:${scrollRequestSequenceRef.current}`;
  }, []);

  const summaryStatusMap = useMemo(
    () =>
      Object.fromEntries(
        (summaryStatuses ?? []).map((item) => [item.chapterId, item])
      ),
    [summaryStatuses]
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
    ]
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
    [allChapters, onChapterSelect, setCurrentChapter]
  );

  const handleOpenInNewTab = useCallback(
    (chapterId: string, title: string) => {
      if (tabs.length >= MAX_TABS) {
        // openTab 内部会处理满的情况
      }
      openTab(chapterId, title);
    },
    [openTab, tabs.length]
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
    [createChapterMutation, isAgentLocked, onChapterSelect, setCurrentChapter, showLockedToast]
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
    [isAgentLocked, showLockedToast, updateChapterMutation]
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
    [isAgentLocked, showLockedToast]
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
    [isAgentLocked, showLockedToast]
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
            dragOrderMap[chapter.id] !== undefined &&
            dragOrderMap[chapter.id] !== chapter.order
        );
        if (!hasChanges) continue;

        const sortedChapterIds = [...volume.chapters]
          .sort(
            (a, b) =>
              (dragOrderMap[a.id] ?? a.order) - (dragOrderMap[b.id] ?? b.order)
          )
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
    [isAgentLocked, showLockedToast, updateVolumeMutation]
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
    [isAgentLocked, moveVolumeMutation, showLockedToast]
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
    [isAgentLocked, showLockedToast]
  );

  const handleConfirmMoveChapter = useCallback(
    async (volumeId: string) => {
      if (!movingChapter) return;
      await moveChapterToVolumeMutation.mutateAsync({
        chapterId: movingChapter.id,
        volumeId,
      });
      setVolumeExpanded(volumeId, true);
      setMoveDialogOpen(false);
      setMovingChapter(null);
    },
    [moveChapterToVolumeMutation, movingChapter, setVolumeExpanded]
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
        onSaveOrder={handleSaveOrder}
        onCancelOrder={handleCancelOrder}
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
            : deletingChapter?.title ?? ""
        }
        onConfirm={handleConfirmDelete}
        loading={deleteChapterMutation.isPending || deleteVolumeMutation.isPending}
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
        chapter={movingChapter}
        volumes={volumes}
        onOpenChange={(open) => {
          setMoveDialogOpen(open);
          if (!open) setMovingChapter(null);
        }}
        onConfirm={handleConfirmMoveChapter}
        loading={moveChapterToVolumeMutation.isPending}
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
          <Dialog.Description size="2" color="gray">
            {editingVolume?.title ?? t("volume.untitled")}
          </Dialog.Description>
          <TextArea
            mt="4"
            value={editingVolumeDescription}
            onChange={(event) => setEditingVolumeDescription(event.target.value)}
            resize="vertical"
            style={{ minHeight: 120 }}
          />
          <Flex justify="end" gap="3" mt="4">
            <Dialog.Close>
              <Button variant="soft" color="gray">
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
