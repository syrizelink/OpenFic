import { Suspense, lazy, useState, useCallback, useRef, useEffect, useMemo } from "react";
import { Box, Flex, Text, IconButton } from "@radix-ui/themes";
import { AtSign, Globe, FileText } from "lucide-react";
import { toast } from "@/components";
import { useEditor, EditorContent } from "@tiptap/react";
import { useTranslation } from "react-i18next";
import { useHotkeys } from "react-hotkeys-hook";
import { useNavigate } from "react-router";
import { AnimatePresence } from "motion/react";
import wordsCount from "words-count";

import { TitleInput, EditorToolbar, Spinner, type EditorToolbarExtraAction } from "@/components";
import { FindReplacePanel } from "./find-replace-panel";
import { ContextMenu } from "@/components";
import { createEditorExtensions } from "../lib/editor-config";
import { useChapter, useUpdateChapter } from "../hooks/use-chapters";
import { useAutoSave } from "../hooks/use-auto-save";
import { useScrollbarAutoHide } from "@/hooks/use-scrollbar-auto-hide";
import { useTabsStore } from "../store/use-tabs-store";
import { createToastThrottler } from "@/lib/ui-utils";
import { buildChapterMentionTag, buildLineRangeMentionTag } from "@/features/assistant/lib/mention-text";
import type { Chapter } from "@/lib/chapter.types";
import { htmlToNewlines, newlinesToHtml } from "@/lib/html-utils";
import {
  createChapterEditorDraft,
  isChapterEditorDraftDirty,
} from "../lib/chapter-editor-draft";

const loadSummaryPanel = () =>
  import("./summary-panel").then((module) => ({ default: module.SummaryPanel }));

const SummaryPanel = lazy(loadSummaryPanel);

const MANUAL_SAVE_EVENT = "openfic:chapter-editor-manual-save";

interface ChapterEditorProps {
  chapterId: string | null;
  onChapterUpdate?: (chapter: Chapter) => void;
  onAddToConversation?: (markup: string) => void;
  projectId?: string;
  isAgentLocked?: boolean;
}

function ChapterEditorInner({
  chapter,
  onChapterUpdate,
  onAddToConversation,
  projectId,
  isAgentLocked = false,
}: {
  chapter: Chapter;
  onChapterUpdate?: (chapter: Chapter) => void;
  onAddToConversation?: (markup: string) => void;
  projectId?: string;
  isAgentLocked?: boolean;
}) {
  const { t } = useTranslation();
  const updateMutation = useUpdateChapter();
  const { containerRef, scrollbarProps } = useScrollbarAutoHide();
  const editorContentRef = useRef<HTMLDivElement>(null);
  const { updateTabTitle } = useTabsStore();
  const navigate = useNavigate();

  const [title, setTitle] = useState(chapter.title);
  const titleRef = useRef(chapter.title);
  const lastSavedDraftRef = useRef(
    createChapterEditorDraft({
      title: chapter.title,
      content: chapter.content,
    })
  );
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [findReplaceMode, setFindReplaceMode] = useState<
    "closed" | "find" | "replace"
  >("closed");
  const [wordCount, setWordCount] = useState(() => wordsCount(chapter.content || ""));
  const saveStatus = isSaving ? "saving" : hasChanges ? "unsaved" : "saved";
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [hasOpenedSummary, setHasOpenedSummary] = useState(false);

  const showLockedToast = useMemo(
    () => createToastThrottler(t("writing.agentLockedChapterEdit")),
    [t]
  );

  useEffect(() => {
    if (!projectId || !chapter.id) return;
    void loadSummaryPanel();
  }, [chapter.id, projectId]);

  const handleWorldInfoClick = useCallback(() => {
    if (projectId) {
      navigate(`/world-info?projectId=${projectId}&from=writing`);
    }
  }, [navigate, projectId]);

  const handleOpenSummary = useCallback(() => {
    setHasOpenedSummary(true);
    setSummaryOpen(true);
  }, []);

  const handleSummaryOpenChange = useCallback((open: boolean) => {
    if (open) setHasOpenedSummary(true);
    setSummaryOpen(open);
  }, []);

  const extraActions: EditorToolbarExtraAction[] = useMemo(() => {
    const actions: EditorToolbarExtraAction[] = [];

    if (projectId) {
      actions.push({
        id: "worldInfo",
        icon: <Globe size={18} />,
        label: t("editor.worldInfo"),
        onClick: handleWorldInfoClick,
      });
    }

    return actions;
  }, [projectId, t, handleWorldInfoClick]);

  const toolbarPrefix = useMemo(() => {
    if (!projectId || !chapter.id) return null;

    return (
      <>
        <IconButton
          variant="ghost"
          size="2"
          aria-label={t("summary.openPanel")}
          onClick={handleOpenSummary}
          onPointerEnter={() => {
            void loadSummaryPanel();
          }}
          onFocus={() => {
            void loadSummaryPanel();
          }}
        >
          <FileText size={18} />
        </IconButton>
        {hasOpenedSummary && (
          <Suspense fallback={null}>
            <SummaryPanel
              projectId={projectId}
              open={summaryOpen}
              onOpenChange={handleSummaryOpenChange}
              trigger={null}
            />
          </Suspense>
        )}
      </>
    );
  }, [projectId, chapter.id, handleOpenSummary, handleSummaryOpenChange, summaryOpen, hasOpenedSummary, t]);

  const openFind = useCallback(() => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }
    setFindReplaceMode("find");
  }, [isAgentLocked, showLockedToast]);

  const openReplace = useCallback(() => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }
    setFindReplaceMode("replace");
  }, [isAgentLocked, showLockedToast]);

  const updateDirtyState = useCallback((nextTitle: string, nextHtmlContent: string) => {
    const nextDraft = createChapterEditorDraft({
      title: nextTitle,
      content: htmlToNewlines(nextHtmlContent),
    });
    setHasChanges(isChapterEditorDraftDirty(lastSavedDraftRef.current, nextDraft));
    return nextDraft;
  }, []);

  const syncDirtyStateFromEditor = useCallback(
    (editorInstance: { getHTML: () => string }) => {
      updateDirtyState(titleRef.current, editorInstance.getHTML());
    },
    [updateDirtyState]
  );

  const editor = useEditor({
    extensions: createEditorExtensions({
      placeholder: t("writing.contentPlaceholder"),
      shortcuts: {
        onFind: openFind,
        onReplace: openReplace,
        onSave: () => {
          if (isAgentLocked) {
            showLockedToast();
            return;
          }
          window.dispatchEvent(new Event(MANUAL_SAVE_EVENT));
        },
      },
    }),
    editable: !isAgentLocked,
    content: chapter.content ? newlinesToHtml(chapter.content) : "",
    onUpdate: ({ editor }) => {
      if (isAgentLocked) return;
      syncDirtyStateFromEditor(editor);
      setWordCount(wordsCount(editor.getText()));
    },
    onCreate: ({ editor }) => {
      setWordCount(wordsCount(editor.getText()));
    },
  });

  const handleSave = useCallback(
    async (isManualSave = false) => {
      if (!editor) return;
      if (isAgentLocked) {
        showLockedToast();
        return;
      }

      const htmlContent = editor.getHTML();
      const draftToSave = createChapterEditorDraft({
        title,
        content: htmlToNewlines(htmlContent),
      });
      const currentWordCount = wordsCount(editor.getText());

      setIsSaving(true);
      try {
        const updatedChapter = await updateMutation.mutateAsync({
          chapterId: chapter.id,
          data: {
            title: draftToSave.title,
            content: draftToSave.content,
            wordCount: currentWordCount,
          },
        });
        lastSavedDraftRef.current = createChapterEditorDraft({
          title: updatedChapter.title,
          content: updatedChapter.content,
        });
        syncDirtyStateFromEditor(editor);
        onChapterUpdate?.(updatedChapter);

        if (isManualSave) {
          toast.success(t("writing.saved"));
        }
      } catch {
        syncDirtyStateFromEditor(editor);
      } finally {
        setIsSaving(false);
      }
    },
    [
      chapter.id,
      editor,
      isAgentLocked,
      onChapterUpdate,
      showLockedToast,
      syncDirtyStateFromEditor,
      t,
      title,
      updateMutation,
    ]
  );

  useEffect(() => {
    titleRef.current = title;
  }, [title]);

  useEffect(() => {
    const handleManualSave = () => {
      void handleSave(true);
    };

    window.addEventListener(MANUAL_SAVE_EVENT, handleManualSave);
    return () => window.removeEventListener(MANUAL_SAVE_EVENT, handleManualSave);
  }, [handleSave]);

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!isAgentLocked);
  }, [editor, isAgentLocked]);

  useEffect(() => {
    if (!editor || hasChanges) return;

    const nextTitle = chapter.title;
    const nextContent = chapter.content ? newlinesToHtml(chapter.content) : "";
    const currentContent = editor.getHTML();
    lastSavedDraftRef.current = createChapterEditorDraft({
      title: nextTitle,
      content: chapter.content,
    });

    if (title !== nextTitle) {
      titleRef.current = nextTitle;
      queueMicrotask(() => {
        setTitle(nextTitle);
        updateTabTitle(chapter.id, nextTitle);
      });
    }

    if (currentContent !== nextContent) {
      editor.commands.setContent(nextContent, { emitUpdate: false });
      queueMicrotask(() => {
        setWordCount(wordsCount(editor.getText()));
      });
    }
  }, [editor, chapter.title, chapter.content, chapter.id, hasChanges, title, updateTabTitle]);

  useEffect(() => {
    if (!editor || !isAgentLocked) return;

    const nextTitle = chapter.title;
    const nextContent = chapter.content ? newlinesToHtml(chapter.content) : "";
    const currentContent = editor.getHTML();
    lastSavedDraftRef.current = createChapterEditorDraft({
      title: nextTitle,
      content: chapter.content,
    });

    if (title !== nextTitle) {
      titleRef.current = nextTitle;
      queueMicrotask(() => {
        setTitle(nextTitle);
        updateTabTitle(chapter.id, nextTitle);
      });
    }

    if (currentContent !== nextContent) {
      editor.commands.setContent(nextContent, { emitUpdate: false });
      queueMicrotask(() => {
        setWordCount(wordsCount(editor.getText()));
      });
    }

    queueMicrotask(() => {
      setHasChanges(false);
    });
  }, [editor, chapter.title, chapter.content, chapter.id, isAgentLocked, title, updateTabTitle]);

  useAutoSave({
    onSave: handleSave,
    hasChanges,
    enabled: !isAgentLocked,
  });

  useHotkeys(
    "mod+s",
    (event) => {
      event.preventDefault();
      if (isAgentLocked) {
        showLockedToast();
        return;
      }
      handleSave(true);
    },
    { enableOnFormTags: true }
  );

  useHotkeys(
    "mod+f",
    (event) => {
      event.preventDefault();
      if (isAgentLocked) {
        showLockedToast();
        return;
      }
      setFindReplaceMode("find");
    },
    { enableOnFormTags: true }
  );

  useHotkeys(
    "mod+h",
    (event) => {
      event.preventDefault();
      if (isAgentLocked) {
        showLockedToast();
        return;
      }
      setFindReplaceMode("replace");
    },
    { enableOnFormTags: true }
  );

  const handleTitleChange = (newTitle: string) => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }
    setTitle(newTitle);
    titleRef.current = newTitle;
    if (editor) {
      updateDirtyState(newTitle, editor.getHTML());
    } else {
      setHasChanges(newTitle !== lastSavedDraftRef.current.title);
    }
    updateTabTitle(chapter.id, newTitle);
  };

  const editorExtraItems = useCallback(() => {
    if (!editor || !onAddToConversation) return [];

    const chapterLabel = chapter.title.trim() || t("writing.untitledChapter");
    const { from, to } = editor.state.selection;
    const selectedText = from === to
      ? ""
      : editor.state.doc.textBetween(from, to, "\n", "\n").trim();
    const hasSelection = selectedText.length > 0;

    return [
      {
        id: "addToConversation",
        label: hasSelection ? t("editor.addSelectedToConversation") : t("editor.addToConversation"),
        icon: AtSign,
        onClick: () => {
          if (!hasSelection) {
            onAddToConversation(buildChapterMentionTag({
              chapterId: chapter.id,
              label: chapterLabel,
            }));
            return;
          }

          const textBeforeSelection = editor.state.doc.textBetween(0, from, "\n", "\n");
          const textBeforeSelectionEnd = editor.state.doc.textBetween(0, to, "\n", "\n");
          const startLine = textBeforeSelection.split("\n").length;
          const endLine = textBeforeSelectionEnd.split("\n").length;

          onAddToConversation(buildLineRangeMentionTag({
            chapterId: chapter.id,
            startLine,
            endLine,
            label: `${chapterLabel} L${startLine}-${endLine}`,
            snapshotText: selectedText,
          }));
        },
      },
    ];
  }, [chapter.id, chapter.title, editor, onAddToConversation, t]);

  const editorMaxWidth = 800;

  return (
    <Box
      style={{
        height: "100%",
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <EditorToolbar
        editor={editor}
        onSave={handleSave}
        isSaving={saveStatus === "saving"}
        hasChanges={hasChanges}
        isAgentLocked={isAgentLocked}
        onLockedAction={showLockedToast}
        extraActions={extraActions}
        toolbarPrefix={toolbarPrefix}
      />

      <AnimatePresence>
        {findReplaceMode !== "closed" && editor && !isAgentLocked && (
          <FindReplacePanel
            key="find-replace-panel"
            editor={editor}
            showReplace={findReplaceMode === "replace"}
            onClose={() => setFindReplaceMode("closed")}
          />
        )}
      </AnimatePresence>

      <Box
        ref={containerRef}
        style={{ flex: 1, minHeight: 0, overflow: "auto" }}
        className={`tiptap-editor-wrapper ${scrollbarProps.className}`}
        onWheel={scrollbarProps.onWheel}
        onMouseMove={scrollbarProps.onMouseMove}
        onMouseLeave={scrollbarProps.onMouseLeave}
        onClick={isAgentLocked ? showLockedToast : undefined}
      >
        <Box
          style={{
            maxWidth: editorMaxWidth,
            margin: "0 auto",
            padding: "0 24px",
          }}
        >
          <TitleInput
            value={title}
            onChange={handleTitleChange}
            onBlur={() => {
              if (hasChanges && !isAgentLocked) {
                handleSave();
              }
            }}
            disabled={isAgentLocked}
            onDisabledClick={showLockedToast}
          />
          <Box style={{ borderBottom: "1px solid var(--gray-a4)" }} />
          <Box py="5" ref={editorContentRef}>
            <EditorContent editor={editor} className="tiptap-editor" />
          </Box>
        </Box>
      </Box>

      {!isAgentLocked && (
        <ContextMenu
          editor={editor}
          containerRef={editorContentRef}
          editorExtraItems={editorExtraItems}
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
        <Text size="1" color="gray">
          {wordCount} {t("writing.words")}
        </Text>
        <Text size="1" color="gray">
          {saveStatus === "saving" && t("writing.saving")}
          {saveStatus === "saved" && t("writing.saved")}
          {saveStatus === "unsaved" && t("writing.unsavedChanges")}
        </Text>
      </Flex>
    </Box>
  );
}

export function ChapterEditor({
  chapterId,
  onChapterUpdate,
  onAddToConversation,
  projectId,
  isAgentLocked = false,
}: ChapterEditorProps) {
  const { t } = useTranslation();
  const { data: chapter, isLoading } = useChapter(chapterId);

  if (!chapterId) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ flex: 1, minHeight: 0 }}
      >
        <Text color="gray" size="3">
          {t("writing.selectChapter")}
        </Text>
      </Flex>
    );
  }

  if (isLoading || !chapter) {
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
    <ChapterEditorInner
      key={chapter.id}
      chapter={chapter}
      onChapterUpdate={onChapterUpdate}
      onAddToConversation={onAddToConversation}
      projectId={projectId}
      isAgentLocked={isAgentLocked}
    />
  );
}
