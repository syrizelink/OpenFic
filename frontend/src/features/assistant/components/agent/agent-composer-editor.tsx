import { useQuery } from "@tanstack/react-query";
import Placeholder from "@tiptap/extension-placeholder";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import type { Editor } from "@tiptap/react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";

import type { AssistantMentionCandidate } from "@/features/assistant/lib/mention-text";
import {
  buildChapterMentionTag,
  buildNoteCategoryMentionTag,
  buildNoteMentionTag,
  buildVolumeMentionTag,
  findActiveMentionQuery,
  mentionTextToHtml,
  parseMentionText,
} from "@/features/assistant/lib/mention-text";
import { searchMentionCandidates } from "@/lib/api-client";

import { MentionNode } from "./extensions/mention-node";
import type { AssistantMentionNodeAttributes } from "./extensions/mention-node";

export type AgentComposerSuggestionStatus = "idle" | "loading" | "empty" | "ready";

const EMPTY_MENTION_CANDIDATES: AssistantMentionCandidate[] = [];

export interface AgentComposerSuggestionState {
  items: AssistantMentionCandidate[];
  selectedIndex: number;
  status: AgentComposerSuggestionStatus;
  onClose: () => void;
  onSelect: (item: AssistantMentionCandidate, index: number) => void;
  onSelectedIndexChange: (index: number) => void;
}

interface AgentComposerEditorProps {
  projectId: string;
  value: string;
  placeholder: string;
  disabled: boolean;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
  onMentionSuggestionsChange?: (state: AgentComposerSuggestionState | null) => void;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

interface MentionQueryState {
  query: string;
  replaceFrom: number;
  visible: boolean;
}

function createClosedMentionQueryState(): MentionQueryState {
  return {
    query: "",
    replaceFrom: -1,
    visible: false,
  };
}

function docToCanonicalText(doc: ProseMirrorNode): string {
  const paragraphs: string[] = [];

  doc.forEach((node) => {
    let current = "";
    node.forEach((child) => {
      if (child.isText) {
        current += child.text ?? "";
        return;
      }
      if (child.type.name === "assistantMention") {
        current += String(child.attrs.mentionRaw ?? "");
      }
    });
    paragraphs.push(current);
  });

  return paragraphs.join("\n");
}

function createMentionNodeAttrs(
  candidate: AssistantMentionCandidate,
): AssistantMentionNodeAttributes {
  const mentionRaw =
    candidate.kind === "volume"
      ? buildVolumeMentionTag({
          volumeId: candidate.id,
          label: candidate.label,
        })
      : candidate.kind === "note"
        ? buildNoteMentionTag({
            noteId: candidate.id,
            label: candidate.label,
          })
        : candidate.kind === "note_category"
          ? buildNoteCategoryMentionTag({
              categoryId: candidate.id,
              label: candidate.label,
            })
          : buildChapterMentionTag({
              chapterId: candidate.id,
              label: candidate.label,
            });

  return {
    mentionKind: candidate.kind,
    mentionLabel: candidate.label,
    mentionRaw,
    mentionBody: "",
    volumeId: candidate.kind === "volume" ? candidate.id : "",
    chapterId: candidate.kind === "chapter" ? candidate.id : "",
    noteId: candidate.kind === "note" ? candidate.id : "",
    noteCategoryId: candidate.kind === "note_category" ? candidate.id : "",
    startLine: "",
    endLine: "",
  };
}

export function AgentComposerEditor({
  projectId,
  value,
  placeholder,
  disabled,
  onOpenMentionChapter,
  onMentionSuggestionsChange,
  onChange,
  onSubmit,
}: AgentComposerEditorProps) {
  const isApplyingExternalValueRef = useRef(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [mentionQuery, setMentionQuery] = useState<MentionQueryState>(
    createClosedMentionQueryState,
  );

  const normalizedMentionQuery = mentionQuery.query.trim();
  const shouldSearchMentionCandidates =
    mentionQuery.visible && normalizedMentionQuery.length > 0 && projectId.trim().length > 0;
  const { data: remoteMentionCandidates, isFetching: isSearchingMentionCandidates } = useQuery({
    queryKey: ["assistant-mention-candidates", projectId, normalizedMentionQuery],
    queryFn: ({ signal }) =>
      searchMentionCandidates(projectId, normalizedMentionQuery, 20, undefined, signal),
    enabled: shouldSearchMentionCandidates,
    staleTime: 30 * 1000,
  });
  const suggestionItems = shouldSearchMentionCandidates
    ? (remoteMentionCandidates ?? EMPTY_MENTION_CANDIDATES)
    : EMPTY_MENTION_CANDIDATES;
  const suggestionStatus: AgentComposerSuggestionStatus | null = !mentionQuery.visible
    ? null
    : normalizedMentionQuery.length === 0
      ? "idle"
      : isSearchingMentionCandidates
        ? "loading"
        : suggestionItems.length > 0
          ? "ready"
          : "empty";
  const effectiveSelectedIndex =
    suggestionStatus === "ready" && suggestionItems.length > 0
      ? Math.min(selectedIndex, suggestionItems.length - 1)
      : 0;

  const extensions = useMemo(
    () => [
      StarterKit.configure({
        heading: false,
        bold: false,
        italic: false,
        strike: false,
        code: false,
        codeBlock: false,
        blockquote: false,
        horizontalRule: false,
        bulletList: false,
        orderedList: false,
        listItem: false,
        hardBreak: false,
      }),
      Placeholder.configure({
        placeholder,
      }),
      MentionNode.configure({
        onOpenMentionChapter,
      }),
    ],
    [onOpenMentionChapter, placeholder],
  );

  const editor = useEditor({
    extensions,
    content: mentionTextToHtml(value),
    editable: !disabled,
    editorProps: {
      attributes: {
        class: "agent-composer-prosemirror",
      },
    },
    onCreate: ({ editor: instance }) => {
      const next = docToCanonicalText(instance.state.doc);
      if (next !== value) {
        isApplyingExternalValueRef.current = true;
        instance.commands.setContent(mentionTextToHtml(value), { emitUpdate: false });
        isApplyingExternalValueRef.current = false;
      }
    },
    onUpdate: ({ editor: instance }) => {
      if (isApplyingExternalValueRef.current) return;
      onChange(docToCanonicalText(instance.state.doc));
      updateMentionQuery(instance);
    },
    onSelectionUpdate: ({ editor: instance }) => {
      updateMentionQuery(instance);
    },
  });

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      if (suggestionStatus !== "ready" || suggestionItems.length === 0) {
        setSelectedIndex(0);
        return;
      }
      setSelectedIndex((current) => Math.min(current, suggestionItems.length - 1));
    });
    return () => {
      cancelled = true;
    };
  }, [suggestionItems.length, suggestionStatus]);

  const updateMentionQuery = useCallback(
    (instance: Editor) => {
      if (disabled) {
        setMentionQuery((current) => (current.visible ? createClosedMentionQueryState() : current));
        return;
      }

      const selection = instance.state.selection;
      if (!selection.empty) {
        setMentionQuery((current) => (current.visible ? createClosedMentionQueryState() : current));
        return;
      }

      const { from, $from } = selection;
      const textBefore = $from.parent.textBetween(0, $from.parentOffset, undefined, "\ufffc");
      const activeQuery = findActiveMentionQuery(textBefore);
      if (!activeQuery) {
        setMentionQuery((current) => (current.visible ? createClosedMentionQueryState() : current));
        return;
      }

      setMentionQuery({
        query: activeQuery.query,
        replaceFrom: from - activeQuery.replaceLength,
        visible: true,
      });
    },
    [disabled],
  );

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!disabled);
  }, [disabled, editor]);

  useEffect(() => {
    if (!editor) return;
    const nextCanonicalText = docToCanonicalText(editor.state.doc);
    if (nextCanonicalText === value) return;
    isApplyingExternalValueRef.current = true;
    editor.commands.setContent(mentionTextToHtml(value), { emitUpdate: false });
    isApplyingExternalValueRef.current = false;
    updateMentionQuery(editor);
  }, [editor, updateMentionQuery, value]);

  useEffect(() => {
    if (!editor) return;
    const parsedSegments = parseMentionText(value);
    const hasOnlyMentions =
      parsedSegments.length > 0 &&
      parsedSegments.every((segment) => typeof segment !== "string" || !segment.trim());
    if (hasOnlyMentions && !value.includes("\n") && !editor.isFocused) {
      editor.commands.focus("end");
    }
  }, [editor, value]);

  const closeSuggestions = useCallback(() => {
    setMentionQuery(createClosedMentionQueryState());
    setSelectedIndex(0);
  }, []);

  const handleSelectSuggestion = useCallback(
    (candidate: AssistantMentionCandidate, index: number) => {
      if (!editor || mentionQuery.replaceFrom < 0) return;
      const attrs = createMentionNodeAttrs(candidate);
      const currentSelectionTo = editor.state.selection.from;
      setSelectedIndex(index);
      editor
        .chain()
        .focus()
        .deleteRange({ from: mentionQuery.replaceFrom, to: currentSelectionTo })
        .insertAssistantMention(attrs)
        .insertContent(" ")
        .run();
      closeSuggestions();
    },
    [closeSuggestions, editor, mentionQuery.replaceFrom],
  );

  const handleEditorKeyDownCapture = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      if (event.key !== "Enter") return;
      if (event.shiftKey) {
        if (!editor) return;
        event.preventDefault();
        editor.commands.splitBlock();
        return;
      }
      if (suggestionStatus === "ready" && suggestionItems.length > 0) return;
      event.preventDefault();
      onSubmit();
    },
    [editor, onSubmit, suggestionItems.length, suggestionStatus],
  );

  useEffect(() => {
    if (!editor) return;
    updateMentionQuery(editor);
  }, [editor, updateMentionQuery]);

  useEffect(() => {
    if (!onMentionSuggestionsChange) return;

    if (!mentionQuery.visible || !suggestionStatus) {
      onMentionSuggestionsChange(null);
      return;
    }

    onMentionSuggestionsChange({
      items: suggestionItems,
      selectedIndex: effectiveSelectedIndex,
      status: suggestionStatus,
      onClose: closeSuggestions,
      onSelect: handleSelectSuggestion,
      onSelectedIndexChange: setSelectedIndex,
    });
  }, [
    closeSuggestions,
    effectiveSelectedIndex,
    handleSelectSuggestion,
    mentionQuery.visible,
    onMentionSuggestionsChange,
    suggestionItems,
    suggestionStatus,
  ]);

  useEffect(
    () => () => {
      onMentionSuggestionsChange?.(null);
    },
    [onMentionSuggestionsChange],
  );

  return (
    <div
      className="agent-composer-editor"
      data-disabled={disabled}
      onKeyDownCapture={handleEditorKeyDownCapture}
    >
      <EditorContent editor={editor} />
    </div>
  );
}
