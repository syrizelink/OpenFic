import { Box, Flex, Text } from "@radix-ui/themes";
import { useEditor, EditorContent } from "@tiptap/react";
import type { Editor } from "@tiptap/react";
import { useCallback, useRef, useEffect } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useTranslation } from "react-i18next";

import { ContextMenu } from "./context-menu";
import { EditorToolbar, type EditorToolbarExtraAction } from "./editor-toolbar";
import { createMarkdownEditorExtensions } from "./markdown-editor-config";
import { TitleInput } from "./title-input";

export interface MarkdownEditorProps {
  title: string;
  onTitleChange: (title: string) => void;
  content: string;
  onContentChange: (markdown: string) => void;
  onSave: () => void;
  isSaving?: boolean;
  hasChanges?: boolean;
  isLocked?: boolean;
  onLockedAction?: () => void;
  placeholder?: string;
  titlePlaceholder?: string;
  extraToolbarActions?: EditorToolbarExtraAction[];
  toolbarPrefix?: React.ReactNode;
  wordCount?: number;
  saveStatusText?: { saving: string; saved: string; unsaved: string };
  wordCountLabel?: string;
  lockedBanner?: React.ReactNode;
  maxWidth?: number;
  editorRef?: React.MutableRefObject<Editor | null>;
}

export function MarkdownEditor({
  title,
  onTitleChange,
  content,
  onContentChange,
  onSave,
  isSaving = false,
  hasChanges = false,
  isLocked = false,
  onLockedAction,
  placeholder,
  titlePlaceholder,
  extraToolbarActions,
  toolbarPrefix,
  wordCount: externalWordCount,
  saveStatusText,
  wordCountLabel,
  lockedBanner,
  maxWidth = 800,
  editorRef: externalEditorRef,
}: MarkdownEditorProps) {
  const { t } = useTranslation();
  const contentSyncedRef = useRef(content);
  const editorContentRef = useRef<HTMLDivElement>(null);

  const editor = useEditor({
    extensions: createMarkdownEditorExtensions({
      placeholder: placeholder ?? "",
      shortcuts: {
        onSave: () => {
          if (isLocked) {
            onLockedAction?.();
            return;
          }
          onSave();
        },
      },
    }),
    content,
    contentType: "markdown",
    editable: !isLocked,
  });
  const editorRef = useRef(editor);

  useEffect(() => {
    editorRef.current = editor;
    if (externalEditorRef) {
      externalEditorRef.current = editor;
    }
  }, [editor, externalEditorRef]);

  useEffect(() => {
    if (!editor) return;
    const onUpdate = () => {
      const markdown = editorRef.current?.getMarkdown();
      if (markdown !== undefined && markdown !== contentSyncedRef.current) {
        contentSyncedRef.current = markdown;
        onContentChange(markdown);
      }
    };
    editor.on("update", onUpdate);
    return () => {
      editor.off("update", onUpdate);
    };
  }, [editor, onContentChange]);

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!isLocked);
  }, [editor, isLocked]);

  useEffect(() => {
    const currentEditor = editorRef.current;
    if (!currentEditor) return;
    if (content === contentSyncedRef.current) return;

    contentSyncedRef.current = content;
    currentEditor.commands.setContent(content, { emitUpdate: false });
  }, [content]);

  useHotkeys(
    "mod+s",
    (event) => {
      event.preventDefault();
      if (isLocked) {
        onLockedAction?.();
        return;
      }
      onSave();
    },
    { enableOnFormTags: true },
  );

  const handleTitleBlur = useCallback(() => {
    if (hasChanges && !isLocked) {
      onSave();
    }
  }, [hasChanges, isLocked, onSave]);

  const saveStatus = isSaving ? "saving" : hasChanges ? "unsaved" : "saved";
  const wordCount = externalWordCount ?? editor?.storage.characterCount?.characters() ?? 0;

  return (
    <Box
      style={{
        height: "100%",
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {lockedBanner}

      <EditorToolbar
        editor={editor}
        onSave={onSave}
        isSaving={isSaving}
        hasChanges={hasChanges}
        isAgentLocked={isLocked}
        onLockedAction={onLockedAction}
        extraActions={extraToolbarActions}
        toolbarPrefix={toolbarPrefix}
      />

      <Box
        style={{ flex: 1, minHeight: 0, overflow: "auto" }}
        className="tiptap-editor-wrapper"
      >
        <Box
          style={{
            maxWidth,
            margin: "0 auto",
            padding: "0 24px",
          }}
        >
          <TitleInput
            value={title}
            onChange={onTitleChange}
            onBlur={handleTitleBlur}
            disabled={isLocked}
            onDisabledClick={onLockedAction}
            placeholder={titlePlaceholder}
          />
          <Box style={{ borderBottom: "1px solid var(--gray-a4)" }} />
          <Box
            py="5"
            ref={editorContentRef}
          >
            <EditorContent
              editor={editor}
              className="tiptap-editor"
            />
          </Box>
        </Box>
      </Box>

      {!isLocked && (
        <ContextMenu
          editor={editor}
          containerRef={editorContentRef}
        />
      )}

      <Flex
        px="6"
        py="3"
        justify="between"
        align="center"
        style={{
          borderTop: "1px solid var(--gray-a4)",
          background: "var(--gray-a2)",
        }}
      >
        <Text
          size="1"
          color="gray"
        >
          {wordCount} {wordCountLabel ?? t("writing.words")}
        </Text>
        <Text
          size="1"
          color="gray"
        >
          {saveStatus === "saving" && (saveStatusText?.saving ?? t("writing.saving"))}
          {saveStatus === "saved" && (saveStatusText?.saved ?? t("writing.saved"))}
          {saveStatus === "unsaved" && (saveStatusText?.unsaved ?? t("writing.unsavedChanges"))}
        </Text>
      </Flex>
    </Box>
  );
}
