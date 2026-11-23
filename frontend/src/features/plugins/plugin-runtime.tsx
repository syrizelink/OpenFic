import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { toast } from "@/components";
import { apiClient, fetchChapter, fetchNote } from "@/lib/api-client";
import { getSocket } from "@/lib/socket-client";

import { pluginsQueryOptions, fetchPluginDevelopment, PLUGINS_QUERY_KEY } from "./api";
import {
  publishLocalEvent,
  applyEditorChange,
  setEditorEventsEnabled,
  type EditorSnapshot,
} from "./frontend-host";
import { enablePluginDiagnostics } from "./plugin-diagnostics";
import { SelectionMenu } from "./selection-menu";

const DATA_QUERY_PREFIXES: Record<string, readonly string[]> = {
  projects: [
    "projects",
    "project",
    "recent-projects",
    "volume-tree",
    "note-tree",
    "characters",
    "world-info-by-project",
  ],
  chapters: [
    "chapter",
    "volume-tree",
    "chapters-search",
    "projects",
    "project",
    "chapter-summary-list",
    "long-term-summaries-page",
  ],
  "chapter-context": ["chapter-summary-list", "long-term-summaries-page", "summary-projection"],
  volumes: ["volume-tree", "projects", "project", "chapters-search"],
  notes: ["note", "note-tree", "notes-search"],
  "note-categories": ["note-tree", "notes-search"],
  "note-items": ["note-tree", "notes-search"],
  characters: ["characters", "character", "character-graph", "characters-search"],
  "character-relationships": ["character-graph"],
  "world-info": [
    "world-info-by-project",
    "world-info-entries",
    "world-info-entry-detail",
    "world-info-entries-search",
  ],
  "world-info-entries": [
    "world-info-entries",
    "world-info-entry-detail",
    "world-info-entries-search",
  ],
  "prompt-chains": [
    "promptChainVersions",
    "promptChainLatest",
    "promptChainVersion",
    "prompt-chain-entry-search",
  ],
  skills: ["skills", "skill-reference-docs"],
  "agent-definitions": ["agent-definitions"],
  "agent-rules": ["agent-rules", "agent-rule-scopes"],
  models: ["models"],
  "model-providers": ["model-providers", "models", "model-provider-catalog"],
  settings: ["settings", "web-search-settings", "audit-details-storage"],
  tasks: ["tasks", "task"],
  import: [
    "projects",
    "project",
    "volume-tree",
    "note-tree",
    "world-info-by-project",
    "world-info-entries",
  ],
};
const COMPOSER_QUERY_PREFIXES = [
  "right-sidebar-picker",
  "assistant-agent-composer-items",
  "assistant-composer-candidates",
];

interface PluginEvent {
  event: string;
  data: unknown;
  pluginId?: string;
}

export function PluginRuntime() {
  const { data: development } = useQuery({
    queryKey: ["plugin-development"],
    queryFn: fetchPluginDevelopment,
    staleTime: 30000,
  });
  useEffect(() => {
    enablePluginDiagnostics(Boolean(development?.inspector));
  }, [development?.inspector]);
  const queryClient = useQueryClient();
  const { data: plugins = [] } = useQuery(pluginsQueryOptions);
  const editorReads = plugins.some(
    (p) => p.status === "enabled" && p.capabilities.includes("editor.read"),
  );
  useEffect(() => {
    setEditorEventsEnabled(editorReads);
    return () => setEditorEventsEnabled(false);
  }, [editorReads]);
  const editorHooks = plugins.some(
    (p) => p.status === "enabled" && p.hooks?.includes("editor.change"),
  );
  useEffect(() => {
    if (!editorHooks) return;
    let timer: ReturnType<typeof setTimeout>;
    const listener = (event: Event) => {
      const item = (event as CustomEvent<PluginEvent>).detail;
      if (item.event !== "editor.change") return;
      clearTimeout(timer);
      timer = setTimeout(() => {
        const snapshot = item.data as EditorSnapshot;
        void apiClient
          .post<{ data: EditorSnapshot }>("/plugins/events/dispatch", {
            event: "editor.change",
            data: snapshot,
          })
          .then(({ data }) => applyEditorChange(snapshot, data.data))
          .catch(() => {});
      }, 250);
    };
    window.addEventListener("openfic:plugin-event", listener);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("openfic:plugin-event", listener);
    };
  }, [editorHooks]);
  useEffect(() => {
    const socket = getSocket();
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let pluginsChanged = false;
    let resync = false;
    const prefixes = new Set<string>();
    const editors = new Set<string>();

    function flush() {
      timer = undefined;
      if (pluginsChanged) {
        pluginsChanged = false;
        void queryClient.invalidateQueries({ queryKey: PLUGINS_QUERY_KEY });
        void queryClient.invalidateQueries({ queryKey: ["agent-tools"] });
      }
      if (resync) {
        resync = false;
        void queryClient.invalidateQueries({ queryKey: ["agent-tools"] });
        void queryClient.invalidateQueries({ queryKey: ["plugin-development"] });
        void queryClient.invalidateQueries({ queryKey: ["plugin-view-url"] });
        void queryClient.invalidateQueries({ queryKey: ["plugin-component-data"] });
      }
      const changed = new Set(prefixes);
      prefixes.clear();
      if (changed.size > 0)
        void queryClient.invalidateQueries({
          predicate: (query) => changed.has(String(query.queryKey[0])),
        });
      const changedEditors = new Set(editors);
      editors.clear();
      // Refresh only the remote entity; reloading working copies can remount the editor.
      for (const query of queryClient
        .getQueryCache()
        .findAll({ queryKey: ["writing-editor"], type: "active" })) {
        const [, kind, id] = query.queryKey;
        if (typeof id !== "string" || (kind !== "chapter" && kind !== "note")) continue;
        if (!changedEditors.has(kind) && !changedEditors.has(`${kind}:${id}`)) continue;
        const request = kind === "chapter" ? fetchChapter(id) : fetchNote(id);
        void request
          .then((entity) => {
            if (stopped) return;
            queryClient.setQueryData(
              query.queryKey,
              (previous: { entity: { updatedAt: string } } | undefined) => {
                if (
                  !previous ||
                  new Date(entity.updatedAt).getTime() <=
                    new Date(previous.entity.updatedAt).getTime()
                )
                  return previous;
                return { ...previous, entity };
              },
            );
          })
          .catch(() => {
            /* Deleted entities are handled by their tree refresh. */
          });
      }
    }

    function schedule() {
      timer ??= setTimeout(flush, 50);
    }

    function handleDataChanged(event: Event) {
      const item = (event as CustomEvent<PluginEvent>).detail;
      if (item.event !== "data.changed" || !item.data || typeof item.data !== "object") return;
      const data = item.data as { path?: string; resync?: boolean };
      if (data.resync) {
        for (const keys of Object.values(DATA_QUERY_PREFIXES))
          for (const key of keys) prefixes.add(key);
        editors.add("chapter");
        editors.add("note");
      } else {
        const parts = typeof data.path === "string" ? data.path.split("/").filter(Boolean) : [];
        const resource = parts.findLast((part) => Object.hasOwn(DATA_QUERY_PREFIXES, part));
        if (!resource) return;
        for (const key of DATA_QUERY_PREFIXES[resource]) prefixes.add(key);
        if (["chapters", "notes", "projects", "import"].includes(resource)) {
          for (const kind of resource === "chapters"
            ? ["chapter"]
            : resource === "notes"
              ? ["note"]
              : ["chapter", "note"]) {
            const isEntity = resource === "chapters" || resource === "notes";
            editors.add(
              isEntity && parts[0] === resource && parts[1] ? `${kind}:${parts[1]}` : kind,
            );
          }
        }
      }
      for (const key of COMPOSER_QUERY_PREFIXES) prefixes.add(key);
      schedule();
    }

    function handlePluginsChanged() {
      pluginsChanged = true;
      schedule();
    }

    function handleResync() {
      resync = true;
      handlePluginsChanged();
      publishLocalEvent("data.changed", { resync: true });
    }

    function handlePluginEvent(item: PluginEvent) {
      publishLocalEvent(item.event, item.data, item.pluginId);
      if (item.event === "ui.toast") {
        const text =
          item.data && typeof item.data === "object" && "text" in item.data
            ? String(item.data.text)
            : "";
        if (text) toast.info(text);
      }
    }

    window.addEventListener("openfic:plugin-event", handleDataChanged);
    socket.on("plugins:changed", handlePluginsChanged);
    socket.on("plugins:event", handlePluginEvent);
    socket.on("plugins:resync", handleResync);
    socket.on("connect", handleResync);
    if (socket.connected) handleResync();
    else if (!socket.active) socket.connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      window.removeEventListener("openfic:plugin-event", handleDataChanged);
      socket.off("plugins:changed", handlePluginsChanged);
      socket.off("plugins:event", handlePluginEvent);
      socket.off("plugins:resync", handleResync);
      socket.off("connect", handleResync);
    };
  }, [queryClient]);
  return <SelectionMenu />;
}
