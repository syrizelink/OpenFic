/**
 * Entry Editor Component
 *
 * 世界书条目编辑器，基于项目 Markdown 编辑器，支持自动保存。
 * 注意：父组件应使用 key={entry.id} 来确保 entry 变化时组件重新挂载。
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import type { Editor } from "@tiptap/react";

import { MarkdownEditor } from "@/components";
import { updateWorldInfoEntry } from "@/lib/api-client";
import { countTokens } from "@/lib/tiktoken-utils";
import type {
  WorldInfoEntry,
  WorldInfoEntryBriefListResponse,
} from "@/lib/world-info.types";

interface EntryEditorProps {
  /** 条目数据 */
  entry: WorldInfoEntry;
  /** 世界书 ID（用于刷新缓存） */
  worldInfoId: string;
  /** 滚动到指定行（1-based） */
  scrollToLine?: number | null;
  /** 滚动完成后回调 */
  onScrollComplete?: () => void;
}

/** 自动保存防抖延迟（毫秒） */
const AUTO_SAVE_DELAY = 1500;

export function EntryEditor({ entry, worldInfoId, scrollToLine, onScrollComplete }: EntryEditorProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [name, setName] = useState(entry.name);
  const [tokenCount, setTokenCount] = useState<number>(entry.tokenCount || 0);
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const savedContentRef = useRef(entry.content);
  const savedNameRef = useRef(entry.name);
  const hasChangesRef = useRef(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isSavingRef = useRef(false);
  const editorRef = useRef<Editor | null>(null);
  const scrolledRef = useRef(false);

  const updateCaches = useCallback(
    (updated: WorldInfoEntry) => {
      queryClient.setQueryData(["world-info-entry-detail", entry.id], updated);
      queryClient.setQueryData(
        ["world-info-entries", worldInfoId],
        (old: WorldInfoEntryBriefListResponse | undefined) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items.map((item) =>
              item.id === updated.id
                ? {
                    ...item,
                    name: updated.name,
                    tokenCount: updated.tokenCount,
                  }
                : item
            ),
          };
        }
      );
    },
    [entry.id, queryClient, worldInfoId]
  );

  const flushSave = useCallback(async () => {
    if (isSavingRef.current || !hasChangesRef.current) return;
    isSavingRef.current = true;
    setIsSaving(true);

    const content = savedContentRef.current;
    const newName = savedNameRef.current;
    const newTokenCount = countTokens(content);
    setTokenCount(newTokenCount);

    try {
      const updated = await updateWorldInfoEntry(entry.id, {
        name: newName,
        content,
        tokenCount: newTokenCount,
      });
      updateCaches(updated);
      hasChangesRef.current = false;
      setHasChanges(false);
    } finally {
      isSavingRef.current = false;
      setIsSaving(false);
    }
  }, [entry.id, updateCaches]);

  const triggerAutoSave = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = setTimeout(() => {
      void flushSave();
    }, AUTO_SAVE_DELAY);
  }, [flushSave]);

  const handleTitleChange = useCallback(
    (newName: string) => {
      setName(newName);
      savedNameRef.current = newName;
      hasChangesRef.current = true;
      setHasChanges(true);
      triggerAutoSave();
    },
    [triggerAutoSave]
  );

  const handleContentChange = useCallback(
    (markdown: string) => {
      savedContentRef.current = markdown;
      setTokenCount(countTokens(markdown));
      hasChangesRef.current = true;
      setHasChanges(true);
      triggerAutoSave();
    },
    [triggerAutoSave]
  );

  const handleSave = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    void flushSave();
  }, [flushSave]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
      if (hasChangesRef.current) {
        void flushSave();
      }
    };
  }, [flushSave]);

  useEffect(() => {
    if (scrollToLine == null || scrollToLine < 1 || scrolledRef.current) return;
    const editor = editorRef.current;
    if (!editor || editor.isDestroyed) return;

    const timer = setTimeout(() => {
      if (editor.isDestroyed) return;
      try {
        const totalLines = editor.state.doc.content.size;
        const lineHeight = 24;
        const targetPos = Math.min((scrollToLine - 1) * lineHeight, totalLines);
        const resolvedPos = editor.state.doc.resolve(targetPos);
        const node = editor.view.domAtPos(resolvedPos.pos);
        if (node.node) {
          const el = node.node.nodeType === Node.TEXT_NODE
            ? node.node.parentElement
            : node.node as HTMLElement;
          el?.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      } finally {
        scrolledRef.current = true;
        onScrollComplete?.();
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [scrollToLine, onScrollComplete]);

  useEffect(() => {
    scrolledRef.current = false;
  }, [entry.id]);

  return (
    <MarkdownEditor
      title={name}
      onTitleChange={handleTitleChange}
      content={entry.content}
      onContentChange={handleContentChange}
      onSave={handleSave}
      isSaving={isSaving}
      hasChanges={hasChanges}
      placeholder={t("worldInfo.contentPlaceholder")}
      titlePlaceholder={t("worldInfo.entryNamePlaceholder")}
      wordCount={tokenCount}
      wordCountLabel={t("worldInfo.tokenCount")}
      editorRef={editorRef}
    />
  );
}
