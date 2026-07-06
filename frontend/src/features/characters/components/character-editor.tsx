import { Flex, Text } from "@radix-ui/themes";
import type { Editor } from "@tiptap/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { MarkdownEditor, Spinner } from "@/components";
import type { Character } from "@/lib/character.types";
import { countTokens } from "@/lib/tiktoken-utils";

const AUTO_SAVE_DELAY = 1500;

interface CharacterEditorProps {
  character: Character | null;
  isSaving?: boolean;
  isLoading?: boolean;
  onSave: (data: { name: string; description: string }) => Promise<void> | void;
}

export function CharacterEditor({
  character,
  isSaving = false,
  isLoading = false,
  onSave,
}: CharacterEditorProps) {
  const { t } = useTranslation();
  const [name, setName] = useState(character?.name ?? "");
  const [description, setDescription] = useState(character?.description ?? "");
  const [tokenCount, setTokenCount] = useState(countTokens(character?.description ?? ""));
  const [hasChanges, setHasChanges] = useState(false);
  const editorRef = useRef<Editor | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestValueRef = useRef({
    name: character?.name ?? "",
    description: character?.description ?? "",
  });
  const hasChangesRef = useRef(false);
  const isSavingRef = useRef(false);

  const flushSave = useCallback(async () => {
    if (!character || isSavingRef.current || !hasChangesRef.current) return;
    const nextName = latestValueRef.current.name.trim();
    if (!nextName) return;

    isSavingRef.current = true;
    try {
      await onSave({ name: nextName, description: latestValueRef.current.description });
      hasChangesRef.current = false;
      setHasChanges(false);
    } catch {
      hasChangesRef.current = true;
      setHasChanges(true);
    } finally {
      isSavingRef.current = false;
    }
  }, [character, onSave]);

  const scheduleSave = useCallback(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      saveTimerRef.current = null;
      void flushSave();
    }, AUTO_SAVE_DELAY);
  }, [flushSave]);

  const handleTitleChange = useCallback(
    (value: string) => {
      setName(value);
      latestValueRef.current.name = value;
      hasChangesRef.current = true;
      setHasChanges(true);
      scheduleSave();
    },
    [scheduleSave],
  );

  const handleContentChange = useCallback(
    (value: string) => {
      setDescription(value);
      setTokenCount(countTokens(value));
      latestValueRef.current.description = value;
      hasChangesRef.current = true;
      setHasChanges(true);
      scheduleSave();
    },
    [scheduleSave],
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
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      if (hasChangesRef.current) void flushSave();
    };
  }, [flushSave]);

  if (isLoading) {
    return (
      <Flex
        className="characters-editor-empty"
        align="center"
        justify="center"
      >
        <Spinner size={18} />
      </Flex>
    );
  }

  if (!character) {
    return (
      <Flex
        className="characters-editor-empty"
        direction="column"
        align="center"
        justify="center"
      >
        <Text
          size="3"
          weight="medium"
        >
          {t("characters.selectCharacter")}
        </Text>
        <Text
          size="2"
          color="gray"
        >
          {t("characters.selectCharacterHint")}
        </Text>
      </Flex>
    );
  }

  return (
    <MarkdownEditor
      title={name}
      onTitleChange={handleTitleChange}
      content={description}
      onContentChange={handleContentChange}
      onSave={handleSave}
      isSaving={isSaving}
      hasChanges={hasChanges}
      placeholder={t("characters.descriptionPlaceholder")}
      titlePlaceholder={t("characters.namePlaceholder")}
      wordCount={tokenCount}
      wordCountLabel={t("characters.tokenCount")}
      editorRef={editorRef}
    />
  );
}
