import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { Box, Flex, IconButton, Tooltip } from "@radix-ui/themes";
import {
  FilePlus,
  FolderPlus,
  ExternalLink,
  AtSign,
  Copy,
  Pencil,
  Lock,
  Unlock,
  EyeOff,
  Eye,
  Trash2,
  Search,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";

import { NoteTree } from "./note-tree";
import { NoteSearchPopover } from "./note-search-popover";
import { ConfirmDialog, ContextMenu, toast } from "@/components";
import type { ContextMenuItem } from "@/components";
import { createToastThrottler } from "@/lib/ui-utils";
import { buildNoteCategoryMentionTag, buildNoteMentionTag } from "@/features/assistant/lib/mention-text";
import {
  useNoteTree,
  useCreateNote,
  useUpdateNote,
  useDeleteNote,
  useCreateNoteCategory,
  useUpdateNoteCategory,
  useDeleteNoteCategory,
  useMoveNoteItem,
  useToggleNoteLock,
  useToggleNoteHidden,
  useDuplicateNote,
} from "../hooks/use-notes";
import type { NoteCategoryItem, NoteListItem, NoteTreeResponse } from "@/lib/note.types";

interface NoteSidebarProps {
  projectId: string;
  onNoteSelect: (noteId: string, title: string) => void;
  onAddToConversation?: (markup: string) => void;
  isAgentLocked?: boolean;
  compact?: boolean;
}

export function NoteSidebar({
  projectId,
  onNoteSelect,
  onAddToConversation,
  isAgentLocked = false,
}: NoteSidebarProps) {
  const { t } = useTranslation();
  const { data } = useNoteTree(projectId);
  const createNoteMutation = useCreateNote(projectId);
  const createCategoryMutation = useCreateNoteCategory(projectId);
  const updateNoteMutation = useUpdateNote(projectId);
  const updateCategoryMutation = useUpdateNoteCategory(projectId);
  const deleteNoteMutation = useDeleteNote(projectId);
  const deleteCategoryMutation = useDeleteNoteCategory(projectId);
  const moveMutation = useMoveNoteItem(projectId);
  const toggleLockMutation = useToggleNoteLock(projectId);
  const toggleHiddenMutation = useToggleNoteHidden(projectId);
  const duplicateNoteMutation = useDuplicateNote(projectId);

  const [contextMenuPos, setContextMenuPos] = useState<{ x: number; y: number } | null>(null);
  const [contextMenuTarget, setContextMenuTarget] = useState<{ id: string; type: "category" | "note"; title: string } | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; type: "category" | "note"; title: string } | null>(null);
  const [currentNoteId, setCurrentNoteId] = useState<string | null>(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);

  const [contentSearchOpen, setContentSearchOpen] = useState(false);
  const [contentSearchExpanded, setContentSearchExpanded] = useState(false);
  const [contentSearchQuery, setContentSearchQuery] = useState("");
  const searchContainerRef = useRef<HTMLDivElement | null>(null);

  const showLockedToast = useMemo(
    () => createToastThrottler(t("writing.agentLockedNoteEdit")),
    [t]
  );

  const handleContextMenu = useCallback(
    (id: string, type: "category" | "note", position: { x: number; y: number }, title: string) => {
      setContextMenuPos(position);
      setContextMenuTarget({ id, type, title });
    },
    []
  );

  const handleCloseContextMenu = useCallback(() => {
    setContextMenuPos(null);
    setContextMenuTarget(null);
  }, []);

  const handleRename = useCallback(() => {
    if (!contextMenuTarget) return;
    setRenamingId(`${contextMenuTarget.type}:${contextMenuTarget.id}`);
    handleCloseContextMenu();
  }, [contextMenuTarget, handleCloseContextMenu]);

  const handleRenameConfirm = useCallback(
    async (id: string, type: "category" | "note", newTitle: string) => {
      setRenamingId(null);
      if (type === "note") {
        await updateNoteMutation.mutateAsync({ noteId: id, data: { title: newTitle } });
        toast.success(t("writing.noteRenamed"));
      } else {
        await updateCategoryMutation.mutateAsync({ categoryId: id, data: { title: newTitle } });
      }
    },
    [updateNoteMutation, updateCategoryMutation, t]
  );

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      if (deleteTarget.type === "note") {
        await deleteNoteMutation.mutateAsync(deleteTarget.id);
      } else {
        await deleteCategoryMutation.mutateAsync(deleteTarget.id);
      }
      setDeleteDialogOpen(false);
      setDeleteTarget(null);
    } catch {
      // handled by mutation
    }
  }, [deleteTarget, deleteNoteMutation, deleteCategoryMutation]);

  const handleNewNote = useCallback(async () => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }
    const targetCategoryId = resolveNewNoteCategoryId(data, selectedCategoryId);
    const note = await createNoteMutation.mutateAsync({
      title: t("writing.untitledNote"),
      categoryId: targetCategoryId,
    });
    setSelectedCategoryId(null);
    setCurrentNoteId(note.id);
    onNoteSelect(note.id, note.title);
  }, [createNoteMutation, isAgentLocked, onNoteSelect, showLockedToast, t, data, selectedCategoryId]);

  const handleNewCategory = useCallback(async () => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }
    await createCategoryMutation.mutateAsync({
      title: t("writing.untitledCategory"),
    });
  }, [createCategoryMutation, isAgentLocked, showLockedToast, t]);

  const handleNoteSelect = useCallback(
    (noteId: string, title: string) => {
      setSelectedCategoryId(null);
      setCurrentNoteId(noteId);
      onNoteSelect(noteId, title);
    },
    [onNoteSelect]
  );

  const handleCategorySelect = useCallback(
    (categoryId: string) => {
      setCurrentNoteId(null);
      setSelectedCategoryId(categoryId);
    },
    []
  );

  const handleOpenInNewTab = useCallback(() => {
    if (!contextMenuTarget || contextMenuTarget.type !== "note") return;
    const target = contextMenuTarget;
    handleCloseContextMenu();
    onNoteSelect(target.id, target.title);
  }, [contextMenuTarget, handleCloseContextMenu, onNoteSelect]);

  const handleAddToConversation = useCallback(() => {
    if (!contextMenuTarget) return;
    const target = contextMenuTarget;
    handleCloseContextMenu();
    if (!onAddToConversation) return;
    const label = target.title.trim() || t("writing.untitledNote");
    if (target.type === "note") {
      onAddToConversation(buildNoteMentionTag({ noteId: target.id, label }));
    } else {
      onAddToConversation(buildNoteCategoryMentionTag({ categoryId: target.id, label }));
    }
  }, [contextMenuTarget, handleCloseContextMenu, onAddToConversation, t]);

  const handleDuplicate = useCallback(async () => {
    if (!contextMenuTarget || contextMenuTarget.type !== "note") return;
    if (isAgentLocked) {
      showLockedToast();
      handleCloseContextMenu();
      return;
    }
    const target = contextMenuTarget;
    handleCloseContextMenu();
try {
        const newNote = await duplicateNoteMutation.mutateAsync(target.id);
        setSelectedCategoryId(null);
        setCurrentNoteId(newNote.id);
        onNoteSelect(newNote.id, newNote.title);
      } catch {
      // handled by mutation
    }
  }, [contextMenuTarget, duplicateNoteMutation, handleCloseContextMenu, isAgentLocked, onNoteSelect, showLockedToast]);

  const handleToggleLock = useCallback(async () => {
    if (!contextMenuTarget || contextMenuTarget.type !== "note") return;
    const note = findNoteInTree(data, contextMenuTarget.id);
    if (!note) {
      handleCloseContextMenu();
      return;
    }
    handleCloseContextMenu();
    await toggleLockMutation.mutateAsync({ noteId: note.id, isLocked: !note.isLocked });
  }, [contextMenuTarget, data, handleCloseContextMenu, toggleLockMutation]);

  const handleToggleHidden = useCallback(async () => {
    if (!contextMenuTarget || contextMenuTarget.type !== "note") return;
    const note = findNoteInTree(data, contextMenuTarget.id);
    if (!note) {
      handleCloseContextMenu();
      return;
    }
    handleCloseContextMenu();
    await toggleHiddenMutation.mutateAsync({ noteId: note.id, isHidden: !note.isHidden });
  }, [contextMenuTarget, data, handleCloseContextMenu, toggleHiddenMutation]);

  const handleMove = useCallback(
    async (itemId: string, kind: "category" | "note", targetCategoryId: string | null) => {
      if (isAgentLocked) {
        showLockedToast();
        return;
      }
      try {
        await moveMutation.mutateAsync({ kind, itemId, targetCategoryId });
      } catch {
        // handled by mutation
      }
    },
    [isAgentLocked, moveMutation, showLockedToast]
  );

  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextMenuTarget) return [];
    const items: ContextMenuItem[] = [];

    if (contextMenuTarget.type === "note") {
      items.push({
        id: "openInNewTab",
        label: t("chapterMenu.openInNewTab"),
        icon: ExternalLink,
        onClick: handleOpenInNewTab,
      });
    }

    items.push({
      id: "addToConversation",
      label: t("chapterMenu.addToConversation"),
      icon: AtSign,
      disabled: !onAddToConversation,
      onClick: handleAddToConversation,
    });

    if (contextMenuTarget.type === "note") {
      items.push({
        id: "duplicate",
        label: t("chapterMenu.duplicate"),
        icon: Copy,
        onClick: () => void handleDuplicate(),
      });
    }

    items.push({
      id: "rename",
      label: t("chapterMenu.rename"),
      icon: Pencil,
      onClick: handleRename,
    });

    if (contextMenuTarget.type === "note") {
      const note = findNoteInTree(data, contextMenuTarget.id);
      if (note) {
        items.push({
          id: "toggleLock",
          label: note.isLocked ? t("writing.noteUnlock") : t("writing.noteLock"),
          icon: note.isLocked ? Unlock : Lock,
          onClick: () => void handleToggleLock(),
        });
        items.push({
          id: "toggleHidden",
          label: note.isHidden ? t("writing.noteShow") : t("writing.noteHide"),
          icon: note.isHidden ? Eye : EyeOff,
          onClick: () => void handleToggleHidden(),
        });
      }
    }

    items.push({
      id: "delete",
      label: t("chapterMenu.delete"),
      icon: Trash2,
      danger: true,
      onClick: () => {
        setDeleteTarget(contextMenuTarget);
        setDeleteDialogOpen(true);
        handleCloseContextMenu();
      },
    });

    return items;
  }, [
    contextMenuTarget,
    data,
    handleAddToConversation,
    handleCloseContextMenu,
    handleDuplicate,
    handleOpenInNewTab,
    handleRename,
    handleToggleHidden,
    handleToggleLock,
    onAddToConversation,
    t,
  ]);

  const handleContentSearchToggle = useCallback(() => {
    setContentSearchExpanded((prev) => {
      if (prev) {
        setContentSearchOpen(false);
        return false;
      }
      return true;
    });
    if (!contentSearchExpanded && contentSearchQuery.trim()) {
      setContentSearchOpen(true);
    }
  }, [contentSearchExpanded, contentSearchQuery]);

  const handleContentSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setContentSearchQuery(e.target.value);
      if (e.target.value.trim()) {
        setContentSearchOpen(true);
      }
    },
    []
  );

  const handleContentSearchFocus = useCallback(() => {
    if (contentSearchQuery.trim()) {
      setContentSearchOpen(true);
    }
  }, [contentSearchQuery]);

  const handleContentSearchBlur = useCallback(() => {
    if (!contentSearchQuery.trim()) {
      setContentSearchExpanded(false);
    }
  }, [contentSearchQuery]);

  const handlePopoverOpenChange = useCallback(
    (open: boolean) => {
      setContentSearchOpen(open);
      if (!open) {
        setContentSearchExpanded(false);
      }
    },
    []
  );

  useEffect(() => {
    if (contentSearchExpanded && searchContainerRef.current) {
      const input = searchContainerRef.current.querySelector("input");
      input?.focus();
    }
  }, [contentSearchExpanded]);

  const handleNavigateToNote = useCallback(
    (noteId: string) => {
      setSelectedCategoryId(null);
      setCurrentNoteId(noteId);
      const title = findNoteTitleInTree(data, noteId);
      onNoteSelect(noteId, title);
    },
    [data, onNoteSelect]
  );

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Box
        px="3"
        py="2"
        style={{
          borderBottom: "1px solid var(--gray-a4)",
        }}
      >
        <Flex gap="0" align="center" justify={contentSearchExpanded ? "start" : "between"}>
          <Box
            ref={searchContainerRef}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 0,
              height: "var(--space-6)",
              paddingRight: contentSearchExpanded ? "var(--space-2)" : 0,
              border: "1px solid transparent",
              borderColor: contentSearchExpanded ? "var(--gray-a7)" : "transparent",
              borderRadius: "max(var(--radius-2), var(--radius-full))",
              background: contentSearchExpanded ? "var(--color-surface)" : "transparent",
              flex: contentSearchExpanded ? 1 : undefined,
              minWidth: 0,
              position: "relative",
              transition: "border-color 0.15s ease, background 0.15s ease, padding-right 0.15s ease",
            }}
          >
            <NoteSearchPopover
              projectId={projectId}
              query={contentSearchQuery}
              open={contentSearchOpen}
              onOpenChange={handlePopoverOpenChange}
              onNavigateToNote={handleNavigateToNote}
            >
              <Box
                style={{
                  position: "absolute",
                  inset: 0,
                  pointerEvents: "none",
                }}
              />
            </NoteSearchPopover>
            <IconButton
              variant="ghost"
              size="2"
              onClick={contentSearchExpanded ? undefined : handleContentSearchToggle}
              style={{
                flexShrink: 0,
                opacity: contentSearchExpanded ? 0.5 : 1,
                transition: "opacity 0.15s ease",
                cursor: contentSearchExpanded ? "default" : undefined,
              }}
            >
              <Search size={16} />
            </IconButton>
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: contentSearchExpanded ? "100%" : 0, opacity: contentSearchExpanded ? 1 : 0 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              style={{ overflow: "hidden" }}
            >
              {contentSearchExpanded && (
                <input
                  type="text"
                  placeholder={t("writing.contentSearchPlaceholder")}
                  value={contentSearchQuery}
                  onChange={handleContentSearchChange}
                  onFocus={handleContentSearchFocus}
                  onBlur={handleContentSearchBlur}
                  style={{
                    width: "100%",
                    border: "none",
                    outline: "none",
                    background: "transparent",
                    fontSize: "var(--font-size-2)",
                    lineHeight: "var(--line-height-2)",
                    color: "var(--gray-12)",
                    padding: 0,
                  }}
                />
              )}
            </motion.div>
          </Box>

          {!contentSearchExpanded && (
            <Flex gap="0" align="center">
              <Tooltip content={t("writing.newNote")}>
                <IconButton variant="ghost" size="2" onClick={() => void handleNewNote()}>
                  <FilePlus size={16} />
                </IconButton>
              </Tooltip>
              <Tooltip content={t("writing.newCategory")}>
                <IconButton variant="ghost" size="2" onClick={() => void handleNewCategory()}>
                  <FolderPlus size={16} />
                </IconButton>
              </Tooltip>
            </Flex>
          )}
        </Flex>
      </Box>

      <NoteTree
        data={data}
        onNoteSelect={handleNoteSelect}
        onCategorySelect={handleCategorySelect}
        currentNoteId={currentNoteId}
        selectedCategoryId={selectedCategoryId}
        renamingId={renamingId}
        onRenameConfirm={handleRenameConfirm}
        onRenameCancel={() => setRenamingId(null)}
        onContextMenu={handleContextMenu}
        onMove={handleMove}
      />

      <ContextMenu
        position={contextMenuPos}
        items={contextMenuItems}
        onClose={handleCloseContextMenu}
      />

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={(open) => {
          setDeleteDialogOpen(open);
          if (!open) setDeleteTarget(null);
        }}
        title={t("chapterMenu.delete")}
        description={
          deleteTarget?.type === "category"
            ? t("writing.deleteCategoryConfirm")
            : deleteTarget?.title ?? ""
        }
        onConfirm={() => void handleDeleteConfirm()}
        loading={deleteNoteMutation.isPending || deleteCategoryMutation.isPending}
      />
    </div>
  );
}

function findNoteInTree(
  data: NoteTreeResponse | undefined,
  noteId: string,
): { id: string; isLocked: boolean; isHidden: boolean } | undefined {
  if (!data) return undefined;
  const walk = (categories: NoteCategoryItem[]): NoteListItem | undefined => {
    for (const cat of categories) {
      const found = cat.notes.find((n) => n.id === noteId);
      if (found) return found;
      const nested = walk(cat.categories);
      if (nested) return nested;
    }
    return undefined;
  };
  const note = walk(data.categories) ?? data.rootNotes.find((n) => n.id === noteId);
  if (!note) return undefined;
  return { id: note.id, isLocked: note.isLocked, isHidden: note.isHidden };
}

function findNoteTitleInTree(
  data: NoteTreeResponse | undefined,
  noteId: string,
): string {
  if (!data) return "";
  const walk = (categories: NoteCategoryItem[]): string | undefined => {
    for (const cat of categories) {
      const found = cat.notes.find((n) => n.id === noteId);
      if (found) return found.title;
      const nested = walk(cat.categories);
      if (nested) return nested;
    }
    return undefined;
  };
  return walk(data.categories) ?? data.rootNotes.find((n) => n.id === noteId)?.title ?? "";
}

function findCategoryDepth(
  categories: NoteCategoryItem[],
  categoryId: string,
  depth = 0,
): number | null {
  for (const cat of categories) {
    if (cat.id === categoryId) return depth;
    const nested = findCategoryDepth(cat.categories, categoryId, depth + 1);
    if (nested !== null) return nested;
  }
  return null;
}

function resolveNewNoteCategoryId(
  data: NoteTreeResponse | undefined,
  selectedCategoryId: string | null,
): string | undefined {
  if (!selectedCategoryId || !data) return undefined;
  const depth = findCategoryDepth(data.categories, selectedCategoryId);
  if (depth === null || depth >= 2) return undefined;
  return selectedCategoryId;
}
