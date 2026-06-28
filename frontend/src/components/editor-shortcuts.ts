import { Extension } from "@tiptap/react";

export interface EditorShortcutCallbacks {
  onFind?: () => void;
  onReplace?: () => void;
  onSave?: () => void;
}

export function createEditorShortcuts(callbacks: EditorShortcutCallbacks) {
  return Extension.create({
    name: "editorShortcuts",

    addKeyboardShortcuts() {
      return {
        "Mod-f": () => {
          callbacks.onFind?.();
          return true;
        },
        "Mod-h": () => {
          callbacks.onReplace?.();
          return true;
        },
        "Mod-s": () => {
          callbacks.onSave?.();
          return true;
        },
      };
    },
  });
}
