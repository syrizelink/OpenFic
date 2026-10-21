import { Box, Flex, Skeleton, Text } from "@radix-ui/themes";
import type { Editor } from "@tiptap/react";
import { useCallback, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";

import { MarkdownEditor } from "@/components";
import { toast } from "@/components/toast";
import { useEditorDraft, type EditorDraft } from "@/hooks/use-editor-draft";
import type { Character } from "@/lib/character.types";
import {
  getEditorContentLimit,
  MAX_EDITOR_CONTENT_CHARACTERS,
  MAX_EDITOR_CONTENT_LINES,
} from "@/lib/editor-content-limits";
import { countTokens } from "@/lib/tiktoken-utils";

interface CharacterEditorProps {
  character: Character | null;
  isLoading?: boolean;
  isAgentLocked?: boolean;
  canSave: () => boolean;
  onSave: (data: { name: string; description: string }) => Promise<Character | null>;
}

export function CharacterEditor({
  character,
  isLoading = false,
  isAgentLocked = false,
  canSave,
  onSave,
}: CharacterEditorProps) {
  const { t } = useTranslation();
  const editorRef = useRef<Editor | null>(null);
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

  const saveDraft = useCallback(
    async ({ title, content }: EditorDraft): Promise<EditorDraft | null> => {
      if (!character || !title.trim()) return null;
      if (!getEditorContentLimit(content).isWithinLimit) {
        showContentLimitToast(content);
        return null;
      }
      rejectedContentRef.current = null;
      const updated = await onSave({ name: title.trim(), description: content });
      return updated ? { title: updated.name, content: updated.description } : null;
    },
    [character, onSave, showContentLimitToast],
  );
  const {
    title: name,
    content: description,
    hasChanges,
    isSaving,
    isSaveBlocked,
    handleTitleChange,
    handleContentChange,
    handleSave,
  } = useEditorDraft({
    key: `character:${character?.id ?? "empty"}`,
    value: { title: character?.name ?? "", content: character?.description ?? "" },
    isLocked: isAgentLocked,
    canSave,
    onSave: saveDraft,
  });
  const tokenCount = useMemo(() => countTokens(description), [description]);

  if (isLoading) {
    return (
      <Box className="characters-editor-loading">
        <Flex
          className="characters-editor-loading-content"
          direction="column"
          gap="4"
        >
          <Skeleton
            width="100%"
            height="36px"
          />
          <Skeleton
            width="100%"
            height="36px"
          />
          <Skeleton
            width="100%"
            height="200px"
          />
          <Skeleton
            width="100%"
            height="80px"
          />
        </Flex>
      </Box>
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
      isSaveBlocked={isSaveBlocked}
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
