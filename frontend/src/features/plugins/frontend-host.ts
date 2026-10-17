import { apiClient } from "@/lib/api-client";

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
export function registerPluginEditor(editor: PluginEditor) {
  activeEditor = editor;
  publishLocalEvent("editor.open", editor.read());
  return () => {
    if (activeEditor === editor) activeEditor = null;
    publishLocalEvent("editor.close", { id: editor.read().id });
  };
}
export function publishLocalEvent(event: string, data: unknown) {
  window.dispatchEvent(new CustomEvent("openfic:plugin-event", { detail: { event, data } }));
}
export function editorSnapshot() {
  return activeEditor?.read() ?? null;
}

export async function frontendCall(
  method: string,
  params: Record<string, unknown>,
  capabilities: string[],
  navigate: (path: string) => void,
) {
  const required = method.startsWith("editor.")
    ? method === "editor.read"
      ? "editor.read"
      : "editor.write"
    : "ui";
  if (!capabilities.includes(required)) throw new Error(`Plugin has not declared ${required}`);
  if (method.startsWith("editor.")) {
    if (!activeEditor) throw new Error("No editor is currently open");
    if (method === "editor.read") return activeEditor.read();
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
    publishLocalEvent("data.changed", params);
    return null;
  }
  if (method === "ui.context")
    return { editor: activeEditor?.read() ?? null, pathname: location.pathname };
  if (method === "ui.tools") return (await apiClient.get("/agent/tools")).data;
  throw new Error(`Unsupported frontend method: ${method}`);
}
