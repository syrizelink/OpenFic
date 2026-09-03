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
  Strikethrough,
  Terminal,
  Undo,
  Underline as UnderlineIcon,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

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
  extraActions?: EditorToolbarExtraAction[];
  toolbarPrefix?: React.ReactNode;
  showMarkdownTools?: boolean;
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
  extraActions,
  toolbarPrefix,
  showMarkdownTools = false,
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
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const scrollContentRef = useRef<HTMLDivElement>(null);
  const pendingLinkSelectionRef = useRef<PendingLinkSelection | null>(null);

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
  }, [editor, showMarkdownTools, updateLeftScrollState]);

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

  return (
    <Box
      className="editor-toolbar"
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

              {showMarkdownTools && (
                <>
                  <LabeledSelect
                    value={headingValue}
                    options={headingOptions}
                    onChange={handleHeadingChange}
                    disabled={isAgentLocked}
                    variant="icon"
                    triggerAriaLabel={t("editor.heading")}
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
            </Flex>
          </Box>
        </Box>

        {showMarkdownTools && leftScrollState.hasOverflow && (
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

        <LinkInputDialog
          open={isLinkDialogOpen}
          initialHref={linkDialogHref}
          onOpenChange={handleLinkDialogOpenChange}
          onSubmit={handleLinkDialogSubmit}
        />
      </Flex>
    </Box>
  );
}
