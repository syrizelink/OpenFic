export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type UIAction = "sidebar.extensions" | "project.toolbar" | "editor.toolbar" | "editor.context" | "editor.panel" | "assistant.toolbar" | "assistant.above-prompt" | "statusbar" | "settings.plugins" | "dashboard";
export interface Context {
  pluginId: string; projectId: string | null; chapterId?: string; noteId?: string;
  language: string; theme: "light" | "dark"; settings: Record<string, Json>;
  capabilities: string[]; slot: UIAction; sdkVersion: string;
}
export interface RequestOptions {
  json?: Json; query?: Record<string, string | number | boolean | undefined>;
  form?: Record<string, string | number>; files?: { field: string; name: string; mime?: string; base64: string }[];
}
export interface Resource<T = Record<string, Json>> {
  list(projectId?: string | null, query?: RequestOptions["query"]): Promise<unknown>;
  get(id: string): Promise<T>; create(values: Record<string, Json>, projectId?: string): Promise<T>;
  update(id: string, values: Record<string, Json>): Promise<T>; delete(id: string): Promise<void>;
}
export interface Store {
  get<T extends Json = Json>(key: string, fallback?: T): Promise<T>;
  set<T extends Json>(key: string, value: T): Promise<T>;
  delete(key: string): Promise<boolean>; keys(prefix?: string): Promise<string[]>;
}
export interface EditorSnapshot {
  kind: "chapter" | "note"; id: string; projectId: string; title: string; content: string;
  selection: { from: number; to: number; text: string }; locked: boolean;
}
export interface ChatMessage { role: "system" | "user" | "assistant" | "tool"; content: string | Json[]; tool_call_id?: string; tool_calls?: Json[]; }
export interface HTTPResponse { status: number; ok: boolean; headers: Record<string, string>; text: string; json: Json; base64: string; }
export interface OpenFicSDK {
  readonly version: string; readonly ready: Promise<Context>; getContext(): Context | undefined;
  call<T = Json>(method: string, params?: Record<string, unknown>): Promise<T>;
  on(event: string, listener: (data: Json, event: string) => void): () => void;
  api: { request<T = Json>(method: string, path: string, options?: RequestOptions): Promise<T>; catalogue(): Promise<Json> };
  data: { projects(): Promise<{ id: string; title: string }[]>; entities(projectId: string): Promise<Json> };
  resource<T = Record<string, Json>>(name: string): Resource<T>;
  projects: Resource; chapters: Resource; volumes: Resource; notes: Resource; characters: Resource;
  storage: Store; secrets: Pick<Store, "set" | "delete" | "keys">;
  files: { read(name: string): Promise<string>; write(name: string, text: string): Promise<void>; delete(name: string): Promise<void>; list(name?: string): Promise<string[]> };
  http: { request(method: string, url: string, options?: { headers?: Record<string,string>; json?: Json; body?: string; form?: Record<string,string> }): Promise<HTTPResponse> };
  models: { complete(messages: ChatMessage[], modelId?: string, options?: { temperature?: number; max_tokens?: number; top_p?: number }): Promise<ChatMessage> };
  workflow: { select(projectId: string, provider: string | null): Promise<Json> };
  hooks: { preview(event: string, data: Record<string, Json>): Promise<Json> };
  events: { on: OpenFicSDK["on"]; emit(event: string, data?: Record<string, Json>): Promise<number> };
  editor: { read(): Promise<EditorSnapshot>; insert(text: string): Promise<EditorSnapshot>; replaceSelection(text: string): Promise<EditorSnapshot>; setContent(text: string): Promise<EditorSnapshot>; setSelection(from: number, to: number): Promise<EditorSnapshot>; focus(): Promise<void>; save(): Promise<void>; undo(): Promise<void>; redo(): Promise<void> };
  ui: { resize(height: number): Promise<number>; navigate(path: string): Promise<void>; openExternal(url: string): Promise<void>; toast(text: string): Promise<void>; confirm(text: string): Promise<boolean>; copy(text: string): Promise<void>; download(name: string, text: string, mime?: string): Promise<void>; context(): Promise<{ editor: EditorSnapshot | null; pathname: string }>; invalidate(): Promise<void> };
  assistant: { fill(text: string): Promise<void> }; log(message: string, level?: "info" | "warning" | "error"): Promise<void>;
  agent: { tools(): Promise<{name:string;description:string;access_level:string;inputSchema:Json}[]>; start(projectId:string,modelId:string,options?:Record<string,Json>):Promise<Json>; send(sessionId:string,message:string,options?:Record<string,Json>):Promise<Json>; cancel(sessionId:string):Promise<Json> };
}
export function getSDK(): OpenFicSDK;
export const OpenFic: OpenFicSDK;
export default OpenFic;
declare global { interface Window { OpenFic: OpenFicSDK; } }
