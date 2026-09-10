import {
  Box,
  Button,
  Dialog,
  Flex,
  IconButton,
  Separator,
  Text,
  TextField,
  Tooltip,
} from "@radix-ui/themes";
import type { Editor } from "@tiptap/react";
import {
  Bold,
  Code,
  CornerDownLeft,
  FileSearch,
  Heading1,
  Heading2,
  Heading3,
  Heading4,
  Heading5,
  Heading6,
  IndentDecrease,
  IndentIncrease,
  Italic,
  Link,
  List,
  ListChecks,
  ListOrdered,
  Pilcrow,
  Quote,
  Redo,
  Save,
  Search,
  Strikethrough,
  Terminal,
  Undo,
  Underline as UnderlineIcon,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getParagraphIndentAction,
  getParagraphOutdentAction,
  getSmartQuoteInsertion,
  isParagraphIndented,
} from "./editor-toolbar-actions";
import { LabeledSelect, type SelectOption } from "./select";
import { Spinner } from "./spinner";

import "./editor-toolbar.css";

export interface EditorToolbarExtraAction {
  id: string;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}

export interface EditorToolbarProps {
  editor: Editor | null;
  onSave: (isManualSave?: boolean) => void;
  isSaving?: boolean;
  hasChanges?: boolean;
  isAgentLocked?: boolean;
  onLockedAction?: () => void;
  onOpenFind?: () => void;
  onOpenReplace?: () => void;
  extraActions?: EditorToolbarExtraAction[];
  toolbarPrefix?: React.ReactNode;
  showMarkdownTools?: boolean;
  showChapterTools?: boolean;
}

interface ToolbarButtonProps {
  icon: React.ReactNode;
  label: string;
  disabled?: boolean;
  active?: boolean;
  onClick: () => void;
}

interface HeadingOptionDefinition {
  value: string;
  labelKey: string;
  icon: LucideIcon;
}

interface PendingLinkSelection {
  from: number;
  to: number;
  isLinkActive: boolean;
}

const HEADING_OPTION_DEFINITIONS: HeadingOptionDefinition[] = [
  { value: "paragraph", labelKey: "editor.paragraph", icon: Pilcrow },
  { value: "1", labelKey: "editor.heading1", icon: Heading1 },
  { value: "2", labelKey: "editor.heading2", icon: Heading2 },
  { value: "3", labelKey: "editor.heading3", icon: Heading3 },
  { value: "4", labelKey: "editor.heading4", icon: Heading4 },
  { value: "5", labelKey: "editor.heading5", icon: Heading5 },
  { value: "6", labelKey: "editor.heading6", icon: Heading6 },
];

const MAX_TASK_ITEM_DEPTH = 3;
const MOBILE_VIEWPORT_QUERY = "(max-width: 767px)";
const MOBILE_KEYBOARD_HEIGHT_THRESHOLD = 150;

const CHAPTER_PUNCTUATION_DEFINITIONS = [
  { id: "comma", symbol: "，", labelKey: "editor.quickPunctuationComma" },
  { id: "period", symbol: "。", labelKey: "editor.quickPunctuationPeriod" },
  { id: "exclamation", symbol: "！", labelKey: "editor.quickPunctuationExclamation" },
  { id: "question", symbol: "？", labelKey: "editor.quickPunctuationQuestion" },
  { id: "colon", symbol: "：", labelKey: "editor.quickPunctuationColon" },
  { id: "semicolon", symbol: "；", labelKey: "editor.quickPunctuationSemicolon" },
  { id: "singleQuote", symbol: "‘", labelKey: "editor.quickPunctuationSingleQuote" },
  { id: "leftQuote", symbol: "“", labelKey: "editor.quickPunctuationLeftQuote" },
] as const;

function getTaskItemDepth(editor: Editor) {
  const { $from } = editor.state.selection;
  let depth = 0;

  for (let level = $from.depth; level > 0; level -= 1) {
    if ($from.node(level).type.name === "taskItem") depth += 1;
  }

  return depth;
}

function ToolbarButton({
  icon,
  label,
  disabled = false,
  active = false,
  onClick,
}: ToolbarButtonProps) {
  return (
    <Tooltip content={label}>
      <IconButton
        variant="ghost"
        size="2"
        type="button"
        disabled={disabled}
        onClick={onClick}
        aria-label={label}
        aria-pressed={active}
        onMouseDown={(event) => event.preventDefault()}
        data-active={active}
        className="editor-toolbar-button"
      >
        {icon}
      </IconButton>
    </Tooltip>
  );
}

interface LinkInputDialogProps {
  open: boolean;
  initialHref: string;
  onOpenChange: (open: boolean) => void;
  onSubmit: (href: string) => void;
}

function LinkInputDialog({ open, initialHref, onOpenChange, onSubmit }: LinkInputDialogProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const [href, setHref] = useState(initialHref);

  useEffect(() => {
    if (open) setHref(initialHref);
  }, [initialHref, open]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit(href);
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <Dialog.Content maxWidth="420px">
        <Dialog.Title>{t("editor.linkDialogTitle")}</Dialog.Title>
        <Dialog.Description
          size="2"
          color="gray"
        >
          {t("editor.linkDialogDescription")}
        </Dialog.Description>

        <form onSubmit={handleSubmit}>
          <Flex
            direction="column"
            gap="2"
            mt="4"
          >
            <Text
              as="label"
              htmlFor={inputId}
              size="2"
              weight="medium"
            >
              {t("editor.linkUrlLabel")}
            </Text>
            <TextField.Root
              id={inputId}
              autoFocus
              value={href}
              placeholder={t("editor.linkUrlPlaceholder")}
              onChange={(event) => setHref(event.target.value)}
            />
          </Flex>

          <Flex
            justify="end"
            gap="3"
            mt="5"
          >
            <Button
              type="button"
              variant="soft"
              color="gray"
              onClick={() => onOpenChange(false)}
            >
              {t("common.cancel")}
            </Button>
            <Button type="submit">{t("common.confirm")}</Button>
          </Flex>
        </form>
      </Dialog.Content>
    </Dialog.Root>
  );
}

export function EditorToolbar({
  editor,
  onSave,
  isSaving,
  hasChanges,
  isAgentLocked = false,
  onLockedAction,
  onOpenFind,
  onOpenReplace,
  extraActions,
  toolbarPrefix,
  showMarkdownTools = false,
  showChapterTools = false,
}: EditorToolbarProps) {
  const { t } = useTranslation();

  const [canUndo, setCanUndo] = useState(() => editor?.can().undo() ?? false);
  const [canRedo, setCanRedo] = useState(() => editor?.can().redo() ?? false);
  const [, forceToolbarUpdate] = useState(0);
  const [isLinkDialogOpen, setIsLinkDialogOpen] = useState(false);
  const [linkDialogHref, setLinkDialogHref] = useState("");
  const [leftScrollState, setLeftScrollState] = useState({
    hasOverflow: false,
    canScrollLeft: false,
    canScrollRight: false,
  });
  const [mobileToolbarState, setMobileToolbarState] = useState(() => ({
    isMobileViewport:
      typeof window !== "undefined" && window.matchMedia(MOBILE_VIEWPORT_QUERY).matches,
    isKeyboardOpen: false,
  }));
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const scrollContentRef = useRef<HTMLDivElement>(null);
  const toolbarRef = useRef<HTMLDivElement>(null);
  const pendingLinkSelectionRef = useRef<PendingLinkSelection | null>(null);
  const largestViewportHeightRef = useRef<number | null>(null);

  const syncMobileKeyboardGeometry = useCallback(() => {
    const toolbar = toolbarRef.current;
    if (!toolbar || typeof window === "undefined") return;

    const visualViewport = window.visualViewport;
    const isKeyboardOpen = toolbar.dataset.mobileKeyboardOpen === "true";
    const keyboardInset =
      isKeyboardOpen && visualViewport
        ? Math.max(0, window.innerHeight - visualViewport.offsetTop - visualViewport.height)
        : 0;

    toolbar.style.setProperty("--editor-toolbar-keyboard-bottom", `${keyboardInset}px`);
    toolbar.parentElement?.style.setProperty(
      "--editor-mobile-keyboard-inset",
      `${keyboardInset}px`,
    );
  }, []);

  const updateMobileToolbarState = useCallback(() => {
    if (!editor || typeof window === "undefined") return;

    const isMobileViewport = window.matchMedia(MOBILE_VIEWPORT_QUERY).matches;
    const visualViewport = window.visualViewport;
    const viewportHeight = visualViewport?.height ?? window.innerHeight;
    const largestViewportHeight = Math.max(
      largestViewportHeightRef.current ?? viewportHeight,
      viewportHeight,
    );
    largestViewportHeightRef.current = largestViewportHeight;
    const keyboardHeight = largestViewportHeight - viewportHeight;
    const isKeyboardOpen = isMobileViewport && keyboardHeight >= MOBILE_KEYBOARD_HEIGHT_THRESHOLD;

    setMobileToolbarState({ isMobileViewport, isKeyboardOpen });
  }, [editor]);

  const updateUndoRedoState = useCallback(() => {
    if (!editor) return;
    setCanUndo(editor.can().undo());
    setCanRedo(editor.can().redo());
    forceToolbarUpdate((version) => version + 1);
  }, [editor]);

  useEffect(() => {
    if (!editor) return;

    editor.on("transaction", updateUndoRedoState);
    editor.on("selectionUpdate", updateUndoRedoState);
    updateUndoRedoState();
    return () => {
      editor.off("transaction", updateUndoRedoState);
      editor.off("selectionUpdate", updateUndoRedoState);
    };
  }, [editor, updateUndoRedoState]);

  useEffect(() => {
    if (!editor || typeof window === "undefined") return;

    largestViewportHeightRef.current = null;
    const mediaQuery = window.matchMedia(MOBILE_VIEWPORT_QUERY);
    const visualViewport = window.visualViewport;
    const handleEditorFocus = () => updateMobileToolbarState();
    const handleEditorBlur = () => updateMobileToolbarState();
    const handleOrientationChange = () => {
      largestViewportHeightRef.current = null;
      updateMobileToolbarState();
    };

    editor.on("focus", handleEditorFocus);
    editor.on("blur", handleEditorBlur);
    window.addEventListener("resize", updateMobileToolbarState);
    window.addEventListener("orientationchange", handleOrientationChange);
    mediaQuery.addEventListener("change", updateMobileToolbarState);
    visualViewport?.addEventListener("resize", updateMobileToolbarState);

    let frameId: number | null = null;
    const scheduleMobileKeyboardGeometry = () => {
      if (frameId !== null) return;
      frameId = window.requestAnimationFrame(() => {
        frameId = null;
        syncMobileKeyboardGeometry();
      });
    };

    visualViewport?.addEventListener("resize", scheduleMobileKeyboardGeometry);
    visualViewport?.addEventListener("scroll", scheduleMobileKeyboardGeometry);
    window.addEventListener("scroll", scheduleMobileKeyboardGeometry, { passive: true });

    updateMobileToolbarState();
    syncMobileKeyboardGeometry();

    return () => {
      editor.off("focus", handleEditorFocus);
      editor.off("blur", handleEditorBlur);
      window.removeEventListener("resize", updateMobileToolbarState);
      window.removeEventListener("orientationchange", handleOrientationChange);
      mediaQuery.removeEventListener("change", updateMobileToolbarState);
      visualViewport?.removeEventListener("resize", updateMobileToolbarState);
      visualViewport?.removeEventListener("resize", scheduleMobileKeyboardGeometry);
      visualViewport?.removeEventListener("scroll", scheduleMobileKeyboardGeometry);
      window.removeEventListener("scroll", scheduleMobileKeyboardGeometry);
      if (frameId !== null) window.cancelAnimationFrame(frameId);
    };
  }, [editor, syncMobileKeyboardGeometry, updateMobileToolbarState]);

  useLayoutEffect(() => {
    syncMobileKeyboardGeometry();
  }, [
    mobileToolbarState.isKeyboardOpen,
    mobileToolbarState.isMobileViewport,
    syncMobileKeyboardGeometry,
  ]);

  useLayoutEffect(() => {
    if (!mobileToolbarState.isKeyboardOpen || typeof document === "undefined") return;

    const documentElement = document.documentElement;
    documentElement.dataset.editorKeyboardOpen = "true";
    return () => {
      delete documentElement.dataset.editorKeyboardOpen;
    };
  }, [mobileToolbarState.isKeyboardOpen]);

  const updateLeftScrollState = useCallback(() => {
    const scrollArea = scrollAreaRef.current;
    if (!scrollArea) return;
    const maxScrollLeft = Math.max(scrollArea.scrollWidth - scrollArea.clientWidth, 0);
    setLeftScrollState({
      hasOverflow: maxScrollLeft > 1,
      canScrollLeft: scrollArea.scrollLeft > 1,
      canScrollRight: maxScrollLeft - scrollArea.scrollLeft > 1,
    });
  }, []);

  useEffect(() => {
    const scrollArea = scrollAreaRef.current;
    const scrollContent = scrollContentRef.current;
    if (!scrollArea) return;

    updateLeftScrollState();
    if (typeof ResizeObserver === "undefined") return;

    const resizeObserver = new ResizeObserver(updateLeftScrollState);
    resizeObserver.observe(scrollArea);
    if (scrollContent) resizeObserver.observe(scrollContent);

    return () => resizeObserver.disconnect();
  }, [editor, showChapterTools, showMarkdownTools, updateLeftScrollState]);

  const handleToolbarWheel = useCallback((event: React.WheelEvent<HTMLDivElement>) => {
    const scrollArea = event.currentTarget;
    if (
      scrollArea.scrollWidth <= scrollArea.clientWidth ||
      Math.abs(event.deltaY) <= Math.abs(event.deltaX)
    ) {
      return;
    }

    scrollArea.scrollLeft += event.deltaY;
    event.preventDefault();
  }, []);

  const handleToolbarPointerDownCapture = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (event.pointerType !== "touch" && event.pointerType !== "pen") return;

      const target = event.target;
      if (target instanceof Element && target.closest(".select-trigger--icon")) return;

      event.preventDefault();
      editor?.view.dom.focus({ preventScroll: true });
    },
    [editor],
  );

  const handleToolbarSelectPointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (event.pointerType !== "touch" && event.pointerType !== "pen") return;

      const target = event.target;
      if (!(target instanceof Element) || !target.closest(".select-trigger--icon")) return;

      event.preventDefault();
      editor?.view.dom.focus({ preventScroll: true });
    },
    [editor],
  );

  const handleHeadingSelectContentFocusCapture = useCallback(() => {
    if (!mobileToolbarState.isKeyboardOpen) return;
    editor?.view.dom.focus({ preventScroll: true });
  }, [editor, mobileToolbarState.isKeyboardOpen]);

  const handleHeadingSelectCloseAutoFocus = useCallback(
    (event: Event) => {
      if (!mobileToolbarState.isKeyboardOpen) return;

      event.preventDefault();
      editor?.view.dom.focus({ preventScroll: true });
    },
    [editor, mobileToolbarState.isKeyboardOpen],
  );

  const handleHeadingSelectTouch = useCallback(() => {
    editor?.view.dom.focus({ preventScroll: true });
  }, [editor]);

  const runEditorAction = useCallback(
    (action: () => boolean | void) => {
      if (isAgentLocked) {
        onLockedAction?.();
        return;
      }
      action();
    },
    [isAgentLocked, onLockedAction],
  );

  if (!editor) return null;

  const headingOptions: SelectOption[] = HEADING_OPTION_DEFINITIONS.map(
    ({ value, labelKey, icon: Icon }) => ({
      value,
      label: t(labelKey),
      prefix: (
        <Icon
          size={18}
          aria-hidden="true"
        />
      ),
    }),
  );

  const headingValue = editor.isActive("heading")
    ? String(editor.getAttributes("heading").level)
    : "paragraph";
  const activeListItemType = showMarkdownTools
    ? editor.isActive("taskItem")
      ? "taskItem"
      : "listItem"
    : "listItem";
  const taskItemDepth =
    showMarkdownTools && activeListItemType === "taskItem" ? getTaskItemDepth(editor) : 0;
  const canIndentListItem =
    showMarkdownTools &&
    (activeListItemType !== "taskItem" || taskItemDepth < MAX_TASK_ITEM_DEPTH) &&
    editor.can().sinkListItem(activeListItemType);
  const canOutdentListItem = showMarkdownTools && editor.can().liftListItem(activeListItemType);
  const currentParagraphStart = editor.state.selection.$from.start();
  const currentParagraphText = editor.state.doc.textBetween(
    currentParagraphStart,
    editor.state.selection.$from.end(),
  );
  const isCurrentParagraphIndented = isParagraphIndented(currentParagraphText);
  const canIndentParagraph = showChapterTools && !isCurrentParagraphIndented;
  const canOutdentParagraph = showChapterTools && isCurrentParagraphIndented;
  const handleHeadingChange = (value: string) => {
    runEditorAction(() => {
      if (value === "paragraph") {
        return editor.chain().focus().setParagraph().run();
      }

      const level = Number(value);
      if (!Number.isInteger(level) || level < 1 || level > 6) return false;
      return editor
        .chain()
        .focus()
        .setHeading({ level: level as 1 | 2 | 3 | 4 | 5 | 6 })
        .run();
    });
  };

  const handleParagraphIndent = () => {
    runEditorAction(() => {
      const action = getParagraphIndentAction(editor.state.selection.$from.start());
      return editor
        .chain()
        .focus()
        .insertContentAt({ from: action.from, to: action.to }, action.text)
        .run();
    });
  };

  const handleParagraphOutdent = () => {
    runEditorAction(() => {
      const { $from } = editor.state.selection;
      const paragraphStart = $from.start();
      const paragraphText = editor.state.doc.textBetween(paragraphStart, $from.end());
      const action = getParagraphOutdentAction(paragraphStart, paragraphText);
      if (!action) return false;

      return editor
        .chain()
        .focus()
        .insertContentAt({ from: action.from, to: action.to }, action.text)
        .run();
    });
  };

  const handleParagraphBreak = () => {
    runEditorAction(() => editor.chain().focus().splitBlock().run());
  };

  const handleChapterPunctuation = (symbol: string) => {
    runEditorAction(() => {
      if (symbol !== "“") {
        return editor.chain().focus().insertContent(symbol).run();
      }

      const { from } = editor.state.selection;
      const insertion = getSmartQuoteInsertion(editor.state.doc.textBetween(0, from));
      const cursorPosition = from + insertion.cursorOffset;
      return editor
        .chain()
        .focus()
        .insertContent(insertion.text)
        .setTextSelection({ from: cursorPosition, to: cursorPosition })
        .run();
    });
  };

  const handleLinkClick = () => {
    if (isAgentLocked) {
      onLockedAction?.();
      return;
    }

    const selection = editor.state.selection;
    const isLinkActive = editor.isActive("link");
    if (selection.empty) {
      if (!isLinkActive) return;
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }

    pendingLinkSelectionRef.current = {
      from: selection.from,
      to: selection.to,
      isLinkActive,
    };
    setLinkDialogHref((editor.getAttributes("link").href as string | undefined) ?? "");
    setIsLinkDialogOpen(true);
  };

  const handleLinkDialogSubmit = (value: string) => {
    if (isAgentLocked) {
      onLockedAction?.();
      return;
    }

    const pendingSelection = pendingLinkSelectionRef.current;
    if (!pendingSelection) return;

    const href = value.trim();
    const chain = editor
      .chain()
      .focus()
      .setTextSelection({ from: pendingSelection.from, to: pendingSelection.to });
    if (pendingSelection.isLinkActive) chain.extendMarkRange("link");
    if (href) chain.setLink({ href }).run();
    else chain.unsetLink().run();

    pendingLinkSelectionRef.current = null;
    setIsLinkDialogOpen(false);
  };

  const handleLinkDialogOpenChange = (open: boolean) => {
    setIsLinkDialogOpen(open);
    if (!open) pendingLinkSelectionRef.current = null;
  };

  const toolbar = (
    <Box
      ref={toolbarRef}
      className="editor-toolbar"
      data-mobile-sidebar-swipe-ignore="true"
      data-mobile-viewport={mobileToolbarState.isMobileViewport}
      data-mobile-keyboard-open={mobileToolbarState.isKeyboardOpen}
      onPointerDownCapture={handleToolbarPointerDownCapture}
      onPointerDown={handleToolbarSelectPointerDown}
      py="2"
      px="6"
    >
      <Flex
        className="editor-toolbar__layout"
        gap="1"
        align="center"
      >
        <Box
          className="editor-toolbar__scroll-container"
          data-can-scroll-left={leftScrollState.canScrollLeft}
          data-can-scroll-right={leftScrollState.canScrollRight}
        >
          <Box
            ref={scrollAreaRef}
            className="editor-toolbar__scroll-area"
            onWheel={handleToolbarWheel}
            onScroll={updateLeftScrollState}
          >
            <Flex
              ref={scrollContentRef}
              className="editor-toolbar__content"
              gap="1"
              align="center"
              justify="start"
            >
              {toolbarPrefix}

              {extraActions?.map((action) => (
                <ToolbarButton
                  key={action.id}
                  icon={action.icon}
                  label={action.label}
                  onClick={action.onClick}
                />
              ))}

              {showChapterTools && (
                <>
                  {CHAPTER_PUNCTUATION_DEFINITIONS.map(({ id, symbol, labelKey }) => (
                    <ToolbarButton
                      key={id}
                      icon={
                        <span
                          className="editor-toolbar__symbol"
                          data-symbol={id}
                          aria-hidden="true"
                        >
                          {symbol}
                        </span>
                      }
                      label={t(labelKey)}
                      disabled={isAgentLocked}
                      onClick={() => handleChapterPunctuation(symbol)}
                    />
                  ))}

                  <ToolbarButton
                    icon={<IndentIncrease size={18} />}
                    label={t("editor.quickIndent")}
                    disabled={isAgentLocked || !canIndentParagraph}
                    onClick={handleParagraphIndent}
                  />
                  <ToolbarButton
                    icon={<IndentDecrease size={18} />}
                    label={t("editor.quickOutdent")}
                    disabled={isAgentLocked || !canOutdentParagraph}
                    onClick={handleParagraphOutdent}
                  />
                  <ToolbarButton
                    icon={<CornerDownLeft size={18} />}
                    label={t("editor.quickNewline")}
                    disabled={isAgentLocked}
                    onClick={handleParagraphBreak}
                  />
                  {onOpenFind && (
                    <ToolbarButton
                      icon={<Search size={18} />}
                      label={t("editor.quickFind")}
                      onClick={onOpenFind}
                    />
                  )}
                  {onOpenReplace && (
                    <ToolbarButton
                      icon={<FileSearch size={18} />}
                      label={t("editor.quickReplace")}
                      onClick={onOpenReplace}
                    />
                  )}
                </>
              )}

              {showMarkdownTools && (
                <>
                  <LabeledSelect
                    value={headingValue}
                    options={headingOptions}
                    onChange={handleHeadingChange}
                    disabled={isAgentLocked}
                    variant="icon"
                    triggerAriaLabel={t("editor.heading")}
                    onContentFocusCapture={handleHeadingSelectContentFocusCapture}
                    onContentCloseAutoFocus={handleHeadingSelectCloseAutoFocus}
                    keepFocusOnTouch={mobileToolbarState.isKeyboardOpen}
                    onTouchTrigger={handleHeadingSelectTouch}
                    preventContentFocus={mobileToolbarState.isKeyboardOpen}
                  />

                  <ToolbarButton
                    icon={<Bold size={18} />}
                    label={t(editor.isActive("bold") ? "editor.removeBold" : "editor.bold")}
                    disabled={isAgentLocked || !editor.can().chain().focus().toggleBold().run()}
                    active={editor.isActive("bold")}
                    onClick={() => runEditorAction(() => editor.chain().focus().toggleBold().run())}
                  />
                  <ToolbarButton
                    icon={<Italic size={18} />}
                    label={t(editor.isActive("italic") ? "editor.removeItalic" : "editor.italic")}
                    disabled={isAgentLocked || !editor.can().chain().focus().toggleItalic().run()}
                    active={editor.isActive("italic")}
                    onClick={() =>
                      runEditorAction(() => editor.chain().focus().toggleItalic().run())
                    }
                  />
                  <ToolbarButton
                    icon={<Strikethrough size={18} />}
                    label={t("editor.strikethrough")}
                    disabled={isAgentLocked || !editor.can().chain().focus().toggleStrike().run()}
                    active={editor.isActive("strike")}
                    onClick={() =>
                      runEditorAction(() => editor.chain().focus().toggleStrike().run())
                    }
                  />
                  <ToolbarButton
                    icon={<UnderlineIcon size={18} />}
                    label={t(
                      editor.isActive("underline") ? "editor.removeUnderline" : "editor.underline",
                    )}
                    disabled={
                      isAgentLocked || !editor.can().chain().focus().toggleUnderline().run()
                    }
                    active={editor.isActive("underline")}
                    onClick={() =>
                      runEditorAction(() => editor.chain().focus().toggleUnderline().run())
                    }
                  />
                  <ToolbarButton
                    icon={<Code size={18} />}
                    label={t("editor.inlineCode")}
                    disabled={isAgentLocked || !editor.can().chain().focus().toggleCode().run()}
                    active={editor.isActive("code")}
                    onClick={() => runEditorAction(() => editor.chain().focus().toggleCode().run())}
                  />

                  <ToolbarButton
                    icon={<Quote size={18} />}
                    label={t("editor.quote")}
                    disabled={isAgentLocked || !editor.can().toggleBlockquote()}
                    active={editor.isActive("blockquote")}
                    onClick={() =>
                      runEditorAction(() => editor.chain().focus().toggleBlockquote().run())
                    }
                  />
                  <ToolbarButton
                    icon={<Terminal size={18} />}
                    label={t("editor.codeBlock")}
                    disabled={
                      isAgentLocked || !editor.can().chain().focus().toggleCodeBlock().run()
                    }
                    active={editor.isActive("codeBlock")}
                    onClick={() =>
                      runEditorAction(() => editor.chain().focus().toggleCodeBlock().run())
                    }
                  />
                  <ToolbarButton
                    icon={<Link size={18} />}
                    label={t(
                      editor.isActive("link") && editor.state.selection.empty
                        ? "editor.removeLink"
                        : "editor.link",
                    )}
                    disabled={
                      isAgentLocked || (editor.state.selection.empty && !editor.isActive("link"))
                    }
                    active={editor.isActive("link")}
                    onClick={handleLinkClick}
                  />

                  <ToolbarButton
                    icon={<List size={18} />}
                    label={t("editor.unorderedList")}
                    disabled={
                      isAgentLocked || !editor.can().chain().focus().toggleBulletList().run()
                    }
                    active={editor.isActive("bulletList")}
                    onClick={() =>
                      runEditorAction(() => editor.chain().focus().toggleBulletList().run())
                    }
                  />
                  <ToolbarButton
                    icon={<ListOrdered size={18} />}
                    label={t("editor.orderedList")}
                    disabled={
                      isAgentLocked || !editor.can().chain().focus().toggleOrderedList().run()
                    }
                    active={editor.isActive("orderedList")}
                    onClick={() =>
                      runEditorAction(() => editor.chain().focus().toggleOrderedList().run())
                    }
                  />
                  <ToolbarButton
                    icon={<ListChecks size={18} />}
                    label={t("editor.taskList")}
                    disabled={isAgentLocked || !editor.can().chain().focus().toggleTaskList().run()}
                    active={editor.isActive("taskList")}
                    onClick={() =>
                      runEditorAction(() => editor.chain().focus().toggleTaskList().run())
                    }
                  />

                  <ToolbarButton
                    icon={<IndentIncrease size={18} />}
                    label={t("editor.indent")}
                    disabled={isAgentLocked || !canIndentListItem}
                    onClick={() =>
                      runEditorAction(() =>
                        editor.chain().focus().sinkListItem(activeListItemType).run(),
                      )
                    }
                  />
                  <ToolbarButton
                    icon={<IndentDecrease size={18} />}
                    label={t("editor.outdent")}
                    disabled={isAgentLocked || !canOutdentListItem}
                    onClick={() =>
                      runEditorAction(() =>
                        editor.chain().focus().liftListItem(activeListItemType).run(),
                      )
                    }
                  />
                </>
              )}
              <Flex
                className="editor-toolbar__right"
                gap="1"
                align="center"
              >
                {(showMarkdownTools || showChapterTools) && leftScrollState.hasOverflow && (
                  <Separator
                    className="editor-toolbar__divider"
                    orientation="vertical"
                    size="1"
                  />
                )}

                <Flex
                  className="editor-toolbar__actions"
                  gap="1"
                  align="center"
                >
                  <ToolbarButton
                    icon={<Undo size={18} />}
                    label={t("editor.undo")}
                    disabled={!canUndo}
                    onClick={() => runEditorAction(() => editor.chain().focus().undo().run())}
                  />
                  <ToolbarButton
                    icon={<Redo size={18} />}
                    label={t("editor.redo")}
                    disabled={!canRedo}
                    onClick={() => runEditorAction(() => editor.chain().focus().redo().run())}
                  />

                  <ToolbarButton
                    icon={isSaving ? <Spinner size={18} /> : <Save size={18} />}
                    label={t("editor.save")}
                    disabled={isSaving || !hasChanges}
                    onClick={() => runEditorAction(() => onSave(true))}
                  />
                </Flex>
              </Flex>
            </Flex>
          </Box>
        </Box>

        <LinkInputDialog
          open={isLinkDialogOpen}
          initialHref={linkDialogHref}
          onOpenChange={handleLinkDialogOpenChange}
          onSubmit={handleLinkDialogSubmit}
        />
      </Flex>
    </Box>
  );

  return toolbar;
}
