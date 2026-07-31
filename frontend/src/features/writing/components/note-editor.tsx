import { Flex, Text } from "@radix-ui/themes";
import { Lock } from "lucide-react";
import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { MarkdownEditor, Spinner } from "@/components";
import { toast } from "@/components/toast";
import { fetchNote } from "@/lib/api-client";
import {
  getEditorContentLimit,
  MAX_EDITOR_CONTENT_CHARACTERS,
  MAX_EDITOR_CONTENT_LINES,
} from "@/lib/editor-content-limits";
import type { Note } from "@/lib/note.types";
import { createToastThrottler } from "@/lib/ui-utils";

import { useAutoSave } from "../hooks/use-auto-save";
import { useUpdateNote } from "../hooks/use-notes";
import {
  shouldShowWritingEditorLoading,
  useWritingEditorEntity,
} from "../hooks/use-writing-editor-entity";
import {
  useWritingWorkingCopy,
  type WritingDraft,
  type WritingWorkingCopyController,
} from "../hooks/use-writing-working-copy";
import {
  areWritingWorkingCopyDraftsEqual,
  getNextWritingWorkingCopyTimestamp,
  isRemoteWritingEntityNewer,
} from "../lib/writing-working-copy";
import { useTabsStore } from "../store/use-tabs-store";

interface NoteEditorProps {
  noteId: string | null;
  scrollTop?: number;
  projectId?: string;
  isAgentLocked?: boolean;
  onScrollPositionChange?: (noteId: string, scrollTop: number) => void;
  onAddToConversation?: (markup: string) => void;
}

interface NoteEditorContentProps {
  note: Note;
  scrollTop: number;
  initialDraft: WritingDraft;
  initialDraftUpdatedAt: Date;
  workingCopy: WritingWorkingCopyController;
  isAgentLocked?: boolean;
  onScrollPositionChange?: (noteId: string, scrollTop: number) => void;
}

function NoteEditorContent({
  note,
  scrollTop,
  initialDraft,
  initialDraftUpdatedAt,
  workingCopy,
  isAgentLocked = false,
  onScrollPositionChange,
}: NoteEditorContentProps) {
  const { t } = useTranslation();
  const updateMutation = useUpdateNote(note.projectId);
  const { updateTabTitle } = useTabsStore();
  const { clearWorkingCopy, persistWorkingCopy } = workingCopy;

  const showLockedToast = useMemo(
    () => createToastThrottler(t("writing.agentLockedNoteEdit")),
    [t],
  );

  const [title, setTitle] = useState(initialDraft.title);
  const titleRef = useRef(initialDraft.title);
  const [hasChanges, setHasChanges] = useState(
    !areWritingWorkingCopyDraftsEqual(initialDraft, { title: note.title, content: note.content }),
  );
  const [isSaving, setIsSaving] = useState(false);
  const [editorContent, setEditorContent] = useState(initialDraft.content);
  const savedContentRef = useRef(initialDraft.content);
  const latestDraftRef = useRef(initialDraft);
  const latestDraftUpdatedAtRef = useRef(initialDraftUpdatedAt);
  const hasChangesRef = useRef(
    !areWritingWorkingCopyDraftsEqual(initialDraft, { title: note.title, content: note.content }),
  );
  const lastSavedDraftRef = useRef<WritingDraft>({
    title: note.title,
    content: note.content,
  });
  const baseUpdatedAtRef = useRef(note.updatedAt);
  const rejectedContentRef = useRef<string | null>(null);

  const showContentLimitToast = useCallback(
    (content: string) => {
      if (rejectedContentRef.current === content) return;
      rejectedContentRef.current = content;
      const { lineCount, characterCount } = getEditorContentLimit(content);
      toast.error(
        t("common.editorContentTooLarge", {
          lineCount,
          characterCount,
          maxLines: MAX_EDITOR_CONTENT_LINES,
          maxCharacters: MAX_EDITOR_CONTENT_CHARACTERS,
        }),
      );
    },
    [t],
  );

  const persistDraft = useCallback(
    (draft: WritingDraft) => {
      latestDraftUpdatedAtRef.current = getNextWritingWorkingCopyTimestamp(
        latestDraftUpdatedAtRef.current,
      );
      persistWorkingCopy(draft, baseUpdatedAtRef.current, latestDraftUpdatedAtRef.current);
    },
    [persistWorkingCopy],
  );

  const handleSave = useCallback(async () => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }

    const draftToSave = latestDraftRef.current;
    const draftUpdatedAt = latestDraftUpdatedAtRef.current;
    const contentLimit = getEditorContentLimit(draftToSave.content);
    if (!contentLimit.isWithinLimit) {
      persistWorkingCopy(draftToSave, baseUpdatedAtRef.current, draftUpdatedAt);
      hasChangesRef.current = true;
      setHasChanges(true);
      showContentLimitToast(draftToSave.content);
      return;
    }
    rejectedContentRef.current = null;

    setIsSaving(true);
    try {
      persistWorkingCopy(draftToSave, baseUpdatedAtRef.current, draftUpdatedAt);
      const updatedNote = await updateMutation.mutateAsync({
        noteId: note.id,
        data: {
          title: draftToSave.title,
          content: draftToSave.content,
        },
      });
      lastSavedDraftRef.current = {
        title: updatedNote.title,
        content: updatedNote.content,
      };
      baseUpdatedAtRef.current = updatedNote.updatedAt;
      void clearWorkingCopy(draftToSave, draftUpdatedAt);
      updateTabTitle(`note:${updatedNote.id}`, latestDraftRef.current.title);
      const isDirty = !areWritingWorkingCopyDraftsEqual(
        latestDraftRef.current,
        lastSavedDraftRef.current,
      );
      hasChangesRef.current = isDirty;
      setHasChanges(isDirty);
    } catch {
      hasChangesRef.current = true;
      setHasChanges(true);
    } finally {
      setIsSaving(false);
    }
  }, [
    clearWorkingCopy,
    isAgentLocked,
    note.id,
    persistWorkingCopy,
    showLockedToast,
    showContentLimitToast,
    updateMutation,
    updateTabTitle,
  ]);

  useEffect(() => {
    titleRef.current = title;
  }, [title]);

  useEffect(() => {
    if (hasChanges || !isRemoteWritingEntityNewer(note.updatedAt, baseUpdatedAtRef.current)) {
      return;
    }

    const draft = { title: note.title, content: note.content ?? "" };
    latestDraftRef.current = draft;
    savedContentRef.current = draft.content;
    setEditorContent(draft.content);
    lastSavedDraftRef.current = draft;
    baseUpdatedAtRef.current = note.updatedAt;
    latestDraftUpdatedAtRef.current = new Date(note.updatedAt);

    if (title !== draft.title) {
      titleRef.current = note.title;
      queueMicrotask(() => {
        setTitle(draft.title);
        updateTabTitle(`note:${note.id}`, note.title);
      });
    }
  }, [note.title, note.content, note.id, note.updatedAt, hasChanges, title, updateTabTitle]);

  useEffect(() => {
    return () => {
      if (hasChangesRef.current) {
        persistWorkingCopy(
          latestDraftRef.current,
          baseUpdatedAtRef.current,
          latestDraftUpdatedAtRef.current,
        );
      }
    };
  }, [persistWorkingCopy]);

  useAutoSave({
    onSave: handleSave,
    hasChanges,
    enabled: !isAgentLocked,
    interval: 3000,
  });

  const handleTitleChange = (newTitle: string) => {
    setTitle(newTitle);
    titleRef.current = newTitle;
    const draft = { title: newTitle, content: savedContentRef.current };
    latestDraftRef.current = draft;
    const isDirty = !areWritingWorkingCopyDraftsEqual(draft, lastSavedDraftRef.current);
    hasChangesRef.current = isDirty;
    setHasChanges(isDirty);
    if (isDirty) {
      persistDraft(draft);
    }
    updateTabTitle(`note:${note.id}`, newTitle);
  };

  const handleContentChange = useCallback(
    (markdown: string) => {
      savedContentRef.current = markdown;
      setEditorContent(markdown);
      const draft = { title, content: markdown };
      latestDraftRef.current = draft;
      const isDirty = !areWritingWorkingCopyDraftsEqual(draft, lastSavedDraftRef.current);
      hasChangesRef.current = isDirty;
      setHasChanges(isDirty);
      if (isDirty) {
        persistDraft(draft);
      }
    },
    [persistDraft, title],
  );

  const handleScrollPositionChange = useCallback(
    (nextScrollTop: number) => {
      onScrollPositionChange?.(note.id, nextScrollTop);
    },
    [note.id, onScrollPositionChange],
  );

  const lockedBanner = note.isLocked ? (
    <Flex
      px="4"
      py="2"
      align="center"
      gap="2"
      style={{
        background: "var(--yellow-a3)",
        borderBottom: "1px solid var(--yellow-a5)",
      }}
    >
      <Lock
        size={14}
        style={{ color: "var(--yellow-10)" }}
      />
      <Text
        size="1"
        style={{ color: "var(--yellow-10)" }}
      >
        {t("writing.noteLocked")}
      </Text>
    </Flex>
  ) : undefined;

  return (
    <MarkdownEditor
      title={title}
      onTitleChange={handleTitleChange}
      content={editorContent}
      onContentChange={handleContentChange}
      onSave={handleSave}
      isSaving={isSaving}
      hasChanges={hasChanges}
      isLocked={isAgentLocked}
      onLockedAction={showLockedToast}
      placeholder={t("writing.noteContentPlaceholder")}
      lockedBanner={lockedBanner}
      scrollTop={scrollTop}
      onScrollPositionChange={handleScrollPositionChange}
    />
  );
}

export function NoteEditor(props: NoteEditorProps) {
  const { t } = useTranslation();
  const { data } = useWritingEditorEntity({
    type: "note",
    entityId: props.noteId,
    fetchEntity: fetchNote,
  });

  if (!props.noteId) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ flex: 1, minHeight: 0 }}
      >
        <Text
          color="gray"
          size="3"
        >
          {t("writing.selectNote")}
        </Text>
      </Flex>
    );
  }

  if (shouldShowWritingEditorLoading(data)) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ flex: 1, minHeight: 0, height: "100%" }}
      >
        <Spinner size={18} />
      </Flex>
    );
  }

  return (
    <NoteEditorWorkingCopy
      key={`${data.entity.id}:${data.draftUpdatedAt.getTime()}`}
      note={data.entity}
      scrollTop={props.scrollTop ?? 0}
      initialDraft={data.draft}
      initialDraftUpdatedAt={data.draftUpdatedAt}
      isAgentLocked={props.isAgentLocked ?? false}
      onScrollPositionChange={props.onScrollPositionChange}
    />
  );
}

function NoteEditorWorkingCopy({
  note,
  scrollTop,
  initialDraft,
  initialDraftUpdatedAt,
  isAgentLocked,
  onScrollPositionChange,
}: Omit<NoteEditorContentProps, "workingCopy">) {
  const workingCopy = useWritingWorkingCopy({
    type: "note",
    entityId: note.id,
  });

  return (
    <NoteEditorContent
      key={`${note.id}:${initialDraftUpdatedAt.getTime()}`}
      note={note}
      scrollTop={scrollTop}
      initialDraft={initialDraft}
      initialDraftUpdatedAt={initialDraftUpdatedAt}
      workingCopy={workingCopy}
      isAgentLocked={isAgentLocked}
      onScrollPositionChange={onScrollPositionChange}
    />
  );
}
