import { Flex, Text } from "@radix-ui/themes";
import type { Editor } from "@tiptap/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { MarkdownEditor, Spinner } from "@/components";
import { toast } from "@/components/toast";
import type { Character } from "@/lib/character.types";
import {
  getEditorContentLimit,
  MAX_EDITOR_CONTENT_CHARACTERS,
  MAX_EDITOR_CONTENT_LINES,
} from "@/lib/editor-content-limits";
import { countTokens } from "@/lib/tiktoken-utils";

const AUTO_SAVE_DELAY = 1500;

interface CharacterEditorProps {
  character: Character | null;
  isSaving?: boolean;
  isLoading?: boolean;
  isAgentLocked?: boolean;
  onSave: (data: { name: string; description: string }) => Promise<void> | void;
}

export function CharacterEditor({
  character,
  isSaving = false,
  isLoading = false,
  isAgentLocked = false,
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

  const flushSave = useCallback(async () => {
    if (!character || isSavingRef.current || !hasChangesRef.current) return;
    const nextName = latestValueRef.current.name.trim();
    if (!nextName) return;
    const description = latestValueRef.current.description;
    const contentLimit = getEditorContentLimit(description);
    if (!contentLimit.isWithinLimit) {
      showContentLimitToast(description);
      return;
    }
    rejectedContentRef.current = null;

    isSavingRef.current = true;
    try {
      await onSave({ name: nextName, description });
      hasChangesRef.current = false;
      setHasChanges(false);
    } catch {
      hasChangesRef.current = true;
      setHasChanges(true);
    } finally {
      isSavingRef.current = false;
    }
  }, [character, onSave, showContentLimitToast]);

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
    if (!character) return;

    if (hasChangesRef.current) return;

    const hasSameContent =
      latestValueRef.current.name === character.name &&
      latestValueRef.current.description === character.description;
    if (hasSameContent) return;

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    setName(character.name);
    setDescription(character.description);
    setTokenCount(countTokens(character.description));
    latestValueRef.current = {
      name: character.name,
      description: character.description,
    };
    hasChangesRef.current = false;
    setHasChanges(false);
  }, [character]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

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
      isLocked={isAgentLocked}
    />
  );
}
