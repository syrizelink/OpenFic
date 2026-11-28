import { buildSelectionMentionTag } from "@/features/assistant/lib/mention-text";
import { apiClient } from "@/lib/api-client";

import type { SelectionSnapshot } from "./selection";

export interface EditorSnapshot {
  kind: "chapter" | "note";
  id: string;
  projectId: string;
  title: string;
  content: string;
  selection: { from: number; to: number; text: string };
  locked: boolean;
}
export interface PluginEditor {
  read: () => EditorSnapshot;
  run: (action: string, params: Record<string, unknown>) => unknown;
}
let activeEditor: PluginEditor | null = null;
let editorEventsEnabled = false;
export function setEditorEventsEnabled(value: boolean) {
  editorEventsEnabled = value;
}
export function hasEditorEventConsumers() {
  return editorEventsEnabled;
}
export function registerPluginEditor(editor: PluginEditor) {
  activeEditor = editor;
  if (editorEventsEnabled) publishLocalEvent("editor.open", editor.read());
  return () => {
    if (activeEditor === editor) activeEditor = null;
    if (editorEventsEnabled) publishLocalEvent("editor.close", { id: editor.read().id });
  };
}
export function publishLocalEvent(event: string, data: unknown, pluginId?: string) {
  window.dispatchEvent(
    new CustomEvent("openfic:plugin-event", { detail: { event, data, pluginId } }),
  );
}
export function editorSnapshot() {
  return activeEditor?.read() ?? null;
}
export async function applyEditorChange(previous: EditorSnapshot, next: EditorSnapshot) {
  const current = activeEditor?.read();
  if (
    activeEditor &&
    current &&
    !current.locked &&
    current.id === previous.id &&
    current.content === previous.content &&
    next.content !== previous.content
  ) {
    await activeEditor.run("setContent", { text: next.content });
  }
}

export async function frontendCall(
  method: string,
  params: Record<string, unknown>,
  capabilities: string[],
  navigate: (path: string) => void,
  pluginId: string,
  onRequestClose?: () => void,
  selectionContext?: SelectionSnapshot,
  overlayContext: Record<string, unknown> = {},
) {
  const required =
    method === "selection.read"
      ? "selection.read"
      : method.startsWith("editor.")
        ? method === "editor.read"
          ? "editor.read"
          : "editor.write"
        : "ui";
  if (!capabilities.includes(required)) throw new Error(`Plugin has not declared ${required}`);
  selectionContext ??= overlayContext.selection as SelectionSnapshot | undefined;
  if (method === "ui.openOverlay" || method === "ui.closeOverlay") {
    if (!capabilities.includes("ui.overlay")) throw new Error("Plugin has not declared ui.overlay");
    const detail: {
      pluginId: string;
      method: string;
      params: Record<string, unknown>;
      context: Record<string, unknown>;
      handled: boolean;
      error?: unknown;
    } = {
      pluginId,
      method,
      params,
      context: overlayContext,
      handled: false,
    };
    window.dispatchEvent(new CustomEvent("openfic:plugin-overlay", { detail }));
    if (detail.error) throw detail.error;
    if (!detail.handled) throw new Error("Plugin overlay host is unavailable");
    return null;
  }
  if (method === "selection.read") return selectionContext ?? null;
  if (method === "assistant.quote") {
    if (!capabilities.includes("selection.read"))
      throw new Error("Plugin has not declared selection.read");
    if (!selectionContext?.target) throw new Error("No matching Agent conversation is available");
    const prompt = params.prompt;
    if (typeof prompt !== "string" || prompt.length > 4000) throw new Error("Invalid quote prompt");
    const data = {
      pluginId,
      prompt,
      source: selectionContext.source,
      target: selectionContext.target,
    };
    const markup = buildSelectionMentionTag(selectionContext.text, data);
    if (markup.length > 48_000) throw new Error("Selection is too large to quote");
    const detail = { ...selectionContext.target, markup, handled: false };
    window.dispatchEvent(new CustomEvent("openfic:assistant-quote", { detail }));
    if (!detail.handled) throw new Error("The selected Agent conversation is no longer available");
    return null;
  }
  if (method === "ui.close") {
    if (!onRequestClose) throw new Error("Closing requires an editor plugin overlay");
    onRequestClose();
    return null;
  }
  if (method.startsWith("editor.")) {
    if (!activeEditor) throw new Error("No editor is currently open");
    if (method === "editor.read") {
      const snapshot = activeEditor.read();
      if (params.summary === true) {
        const { content, selection, ...metadata } = snapshot;
        return {
          ...metadata,
          contentLength: content.length,
          selection: { ...selection, text: selection.text.slice(0, 1000) },
        };
      }
      return snapshot;
    }
    if (activeEditor.read().locked) throw new Error("Editor is locked by an Agent");
    return activeEditor.run(method.slice(7), params);
  }
  if (method === "ui.navigate") {
    const path = String(params.path);
    if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\"))
      throw new Error("Navigation requires a local path");
    navigate(path);
    return null;
  }
  if (method === "ui.openExternal") {
    const url = new URL(String(params.url));
    if (
      url.protocol !== "https:" &&
      !(url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname))
    )
      throw new Error("Unsupported external URL");
    window.open(url.href, "_blank", "noopener,noreferrer");
    return null;
  }
  if (method === "ui.toast") {
    const { toast } = await import("@/components");
    toast.info(String(params.text).slice(0, 1000));
    return null;
  }
  if (method === "ui.confirm") return window.confirm(String(params.text));
  if (method === "ui.copy") {
    await navigator.clipboard.writeText(String(params.text));
    return null;
  }
  if (method === "ui.download") {
    const url = URL.createObjectURL(
      new Blob([String(params.text ?? "")], { type: String(params.mime ?? "text/plain") }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = String(params.name ?? "plugin-export.txt");
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return null;
  }
  if (method === "assistant.fill") {
    publishLocalEvent("assistant.fill", { text: String(params.text) });
    return null;
  }
  if (method === "ui.invalidate") {
    if (params.viewId !== undefined && (typeof params.viewId !== "string" || !params.viewId))
      throw new Error("Invalid plugin view ID");
    publishLocalEvent(
      "ui.invalidate",
      params.viewId === undefined ? {} : { viewId: params.viewId },
      pluginId,
    );
    return null;
  }
  if (method === "ui.context")
    return {
      editor: capabilities.includes("editor.read") ? (activeEditor?.read() ?? null) : null,
      pathname: location.pathname,
    };
  if (method === "ui.tools") return (await apiClient.get("/agent/tools")).data;
  throw new Error(`Unsupported frontend method: ${method}`);
}
