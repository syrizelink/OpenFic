import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { Flex, Text } from "@radix-ui/themes";
import { Lock } from "lucide-react";
import { useTranslation } from "react-i18next";

import { MarkdownEditor, Spinner } from "@/components";
import { useNote, useUpdateNote } from "../hooks/use-notes";
import { useAutoSave } from "../hooks/use-auto-save";
import { useTabsStore } from "../store/use-tabs-store";
import { createToastThrottler } from "@/lib/ui-utils";

interface NoteEditorProps {
  noteId: string | null;
  projectId?: string;
  isAgentLocked?: boolean;
  onAddToConversation?: (markup: string) => void;
}

function NoteEditorInner({
  note,
  isAgentLocked = false,
}: {
  note: NonNullable<ReturnType<typeof useNote>["data"]>;
  isAgentLocked?: boolean;
}) {
  const { t } = useTranslation();
  const updateMutation = useUpdateNote(note.projectId);
  const { updateTabTitle } = useTabsStore();

  const showLockedToast = useMemo(
    () => createToastThrottler(t("writing.agentLockedNoteEdit")),
    [t]
  );

  const [title, setTitle] = useState(note.title);
  const titleRef = useRef(note.title);
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const savedContentRef = useRef(note.content ?? "");

  const handleSave = useCallback(
    async () => {
      if (isAgentLocked) {
        showLockedToast();
        return;
      }

      const markdown = savedContentRef.current;

      setIsSaving(true);
      try {
        const updatedNote = await updateMutation.mutateAsync({
          noteId: note.id,
          data: {
            title,
            content: markdown,
          },
        });
        updateTabTitle(`note:${updatedNote.id}`, updatedNote.title);
        setHasChanges(false);
      } finally {
        setIsSaving(false);
      }
    },
    [note.id, title, updateMutation, updateTabTitle, isAgentLocked, showLockedToast]
  );

  useEffect(() => {
    titleRef.current = title;
  }, [title]);

  useEffect(() => {
    if (!hasChanges) return;

    if (title !== note.title) {
      titleRef.current = note.title;
      queueMicrotask(() => {
        setTitle(note.title);
        updateTabTitle(`note:${note.id}`, note.title);
      });
    }

    if (note.content !== savedContentRef.current) {
      savedContentRef.current = note.content ?? "";
    }
  }, [note.title, note.content, note.id, hasChanges, title, updateTabTitle]);

  useEffect(() => {
    if (!isAgentLocked) return;

    if (title !== note.title) {
      titleRef.current = note.title;
      queueMicrotask(() => {
        setTitle(note.title);
        updateTabTitle(`note:${note.id}`, note.title);
      });
    }

    savedContentRef.current = note.content ?? "";

    queueMicrotask(() => {
      setHasChanges(false);
    });
  }, [note.title, note.content, note.id, isAgentLocked, title, updateTabTitle]);

  useAutoSave({
    onSave: handleSave,
    hasChanges,
    enabled: !isAgentLocked,
    interval: 3000,
  });

  const handleTitleChange = (newTitle: string) => {
    setTitle(newTitle);
    titleRef.current = newTitle;
    setHasChanges(newTitle !== note.title || savedContentRef.current !== note.content);
    updateTabTitle(`note:${note.id}`, newTitle);
  };

  const handleContentChange = useCallback(
    (markdown: string) => {
      savedContentRef.current = markdown;
      setHasChanges(markdown !== note.content || title !== note.title);
    },
    [note.content, note.title, title]
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
      <Lock size={14} style={{ color: "var(--yellow-10)" }} />
      <Text size="1" style={{ color: "var(--yellow-10)" }}>
        {t("writing.noteLocked")}
      </Text>
    </Flex>
  ) : undefined;

  return (
    <MarkdownEditor
      title={title}
      onTitleChange={handleTitleChange}
      content={note.content ?? ""}
      onContentChange={handleContentChange}
      onSave={handleSave}
      isSaving={isSaving}
      hasChanges={hasChanges}
      isLocked={isAgentLocked}
      onLockedAction={showLockedToast}
      placeholder={t("writing.noteContentPlaceholder")}
      lockedBanner={lockedBanner}
    />
  );
}

export function NoteEditor(props: NoteEditorProps) {
  const { t } = useTranslation();
  const { data: note, isLoading } = useNote(props.noteId);

  if (!props.noteId) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ flex: 1, minHeight: 0 }}
      >
        <Text color="gray" size="3">
          {t("writing.selectNote")}
        </Text>
      </Flex>
    );
  }

  if (isLoading || !note) {
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
    <NoteEditorInner
      key={note.id}
      note={note}
      isAgentLocked={props.isAgentLocked ?? false}
    />
  );
}
