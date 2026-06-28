import { useState, useEffect, useCallback } from "react";
import { Box, Flex, IconButton, Separator, Tooltip } from "@radix-ui/themes";
import { Undo, Redo, Save } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Editor } from "@tiptap/react";

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
}

interface ToolbarButtonProps {
  icon: React.ReactNode;
  label: string;
  disabled?: boolean;
  onClick: () => void;
}

function ToolbarButton({
  icon,
  label,
  disabled = false,
  onClick,
}: ToolbarButtonProps) {
  return (
    <Tooltip content={label}>
      <IconButton
        variant="ghost"
        size="2"
        disabled={disabled}
        onClick={onClick}
        aria-label={label}
      >
        {icon}
      </IconButton>
    </Tooltip>
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
}: EditorToolbarProps) {
  const { t } = useTranslation();

  const [canUndo, setCanUndo] = useState(() => editor?.can().undo() ?? false);
  const [canRedo, setCanRedo] = useState(() => editor?.can().redo() ?? false);

  const updateUndoRedoState = useCallback(() => {
    if (!editor) return;
    setCanUndo(editor.can().undo());
    setCanRedo(editor.can().redo());
  }, [editor]);

  useEffect(() => {
    if (!editor) return;

    editor.on("transaction", updateUndoRedoState);
    return () => {
      editor.off("transaction", updateUndoRedoState);
    };
  }, [editor, updateUndoRedoState]);

  const runEditorAction = useCallback(
    (action: () => void) => {
      if (isAgentLocked) {
        onLockedAction?.();
        return;
      }
      action();
    },
    [isAgentLocked, onLockedAction]
  );

  if (!editor) return null;

  return (
    <Box
      py="2"
      px="6"
      style={{
        background: "var(--color-background)",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}
    >
      <Flex gap="1" align="center" justify="end">
        {toolbarPrefix}

        {extraActions?.map((action) => (
          <ToolbarButton
            key={action.id}
            icon={action.icon}
            label={action.label}
            onClick={action.onClick}
          />
        ))}

        {extraActions && extraActions.length > 0 && (
          <Separator orientation="vertical" size="1" />
        )}

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

        <Separator orientation="vertical" size="1" />

        <ToolbarButton
          icon={<Save size={18} />}
          label={t("editor.save")}
          disabled={isSaving || !hasChanges}
          onClick={() => runEditorAction(() => onSave(true))}
        />
      </Flex>
    </Box>
  );
}
