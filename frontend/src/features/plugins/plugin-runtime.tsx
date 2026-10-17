import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { apiClient } from "@/lib/api-client";

import { fetchPlugins, PLUGINS_QUERY_KEY } from "./api";
import { publishLocalEvent, applyEditorChange, type EditorSnapshot } from "./frontend-host";

export function PluginRuntime() {
  const queryClient = useQueryClient();
  const { data: plugins = [] } = useQuery({
    queryKey: PLUGINS_QUERY_KEY,
    queryFn: fetchPlugins,
    refetchInterval: 5000,
  });
  const enabled = plugins.some((p) => p.status === "enabled");
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
      if ((event as CustomEvent).detail.event === "data.changed")
        void queryClient.invalidateQueries({
          predicate: (q) => !["plugins", "plugin-view-url"].includes(String(q.queryKey[0])),
        });
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
