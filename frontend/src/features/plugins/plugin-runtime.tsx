import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { apiClient, fetchChapter, fetchNote } from "@/lib/api-client";

import { fetchPlugins, fetchPluginDevelopment, PLUGINS_QUERY_KEY } from "./api";
import {
  publishLocalEvent,
  applyEditorChange,
  setEditorEventsEnabled,
  type EditorSnapshot,
} from "./frontend-host";
import { enablePluginDiagnostics } from "./plugin-diagnostics";

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
  const { data: plugins = [] } = useQuery({
    queryKey: PLUGINS_QUERY_KEY,
    queryFn: fetchPlugins,
    refetchInterval: 5000,
  });
  const enabled = plugins.some((p) => p.status === "enabled");
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
      const item = (event as CustomEvent).detail;
      if (item.event !== "editor.change") return;
      clearTimeout(timer);
      timer = setTimeout(() => {
        void apiClient
          .post<{ data: EditorSnapshot }>("/plugins/events/dispatch", {
            event: "editor.change",
            data: item.data,
          })
          .then(({ data }) => applyEditorChange(item.data, data.data))
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
    const listener = (event: Event) => {
      if ((event as CustomEvent).detail.event === "data.changed") {
        void queryClient.invalidateQueries({
          predicate: (q) =>
            !["plugins", "plugin-view-url", "writing-editor"].includes(String(q.queryKey[0])),
        });
        // Re-running the working-copy loader changes its draft timestamp/key,
        // remounting Tiptap after the user's own autosave. Refresh only entity
        // data, so the existing remote-change guards preserve drafts and undo.
        for (const query of queryClient
          .getQueryCache()
          .findAll({ queryKey: ["writing-editor"], type: "active" })) {
          const [, kind, id] = query.queryKey;
          if (typeof id !== "string" || !["chapter", "note"].includes(String(kind))) continue;
          const request = kind === "chapter" ? fetchChapter(id) : fetchNote(id);
          void request
            .then((entity) => {
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
              /* Deleted entities are handled by their normal tree refresh. */
            });
        }
      }
    };
    window.addEventListener("openfic:plugin-event", listener);
    return () => window.removeEventListener("openfic:plugin-event", listener);
  }, [queryClient]);
  useEffect(() => {
    if (!enabled) return;
    let stopped = false,
      cursor: number | undefined;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const { data } = await apiClient.get<{
          cursor: number;
          events: { event: string; data: unknown; pluginId?: string }[];
        }>("/plugins/events", { params: { after: cursor } });
        if (stopped) return;
        cursor = data.cursor;
        for (const item of data.events) {
          publishLocalEvent(item.event, item.data);
          if (item.event === "ui.toast") {
            const { toast } = await import("@/components");
            toast.info(String((item.data as { text?: string }).text ?? ""));
          }
        }
      } catch {
        /* The next poll resumes after reconnect. */
      }
      if (!stopped) timer = setTimeout(() => void poll(), 2000);
    }
    void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [enabled, queryClient]);
  return null;
}
