import { useThemeContext } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { apiClient, getApiBaseUrl } from "@/lib/api-client";

import "@/features/app-shell/components/status-bar.css";

import { pluginsQueryOptions, type InstalledPlugin, type PluginView } from "./api";
import { EditorPluginOverlayButton } from "./editor-plugin-actions";
import { PluginIcon } from "./plugin-icon";
import { shouldRefreshPluginView } from "./plugin-refresh";

type StatusPart =
  | { type: "text"; text: string }
  | { type: "icon"; name: string }
  | { type: "asset"; path: string };

export function PluginStatusItems() {
  const { data: plugins = [] } = useQuery(pluginsQueryOptions);
  const entries = plugins
    .filter((plugin) => plugin.status === "enabled")
    .flatMap((plugin) =>
      plugin.views.filter((view) => view.slot === "statusbar").map((view) => ({ plugin, view })),
    );
  if (!entries.length) return null;
  return (
    <div
      className="app-status-bar__plugin-items"
      data-plugin-slot="statusbar"
    >
      {entries.map(({ plugin, view }) => (
        <PluginStatusItem
          key={`${plugin.id}:${plugin.version}:${plugin.reload_revision}:${view.id}`}
          plugin={plugin}
          view={view}
        />
      ))}
    </div>
  );
}

export function PluginStatusItem({ plugin, view }: { plugin: InstalledPlugin; view: PluginView }) {
  const { i18n } = useTranslation();
  const { appearance } = useThemeContext();
  const context = { language: i18n.language, theme: appearance === "dark" ? "dark" : "light" };
  const { data, refetch } = useQuery({
    queryKey: [
      "plugin-status",
      plugin.id,
      plugin.version,
      plugin.reload_revision,
      view.id,
      context.language,
      context.theme,
    ],
    queryFn: async ({ signal }) =>
      (
        await apiClient.post<{ items: StatusPart[] }>(
          `/plugins/${encodeURIComponent(plugin.id)}/views/${encodeURIComponent(view.id)}/status`,
          { context },
          { signal },
        )
      ).data,
    refetchOnWindowFocus: false,
    retry: false,
  });
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    function invalidate(event: Event) {
      const detail = (
        event as CustomEvent<{
          event: string;
          pluginId?: string;
          data?: { viewId?: string; resync?: boolean };
        }>
      ).detail;
      if (!shouldRefreshPluginView(detail, plugin.id, view.id, plugin.capabilities)) return;
      clearTimeout(timer);
      timer = setTimeout(() => void refetch(), 50);
    }
    window.addEventListener("openfic:plugin-event", invalidate);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("openfic:plugin-event", invalidate);
    };
  }, [plugin.id, plugin.capabilities, view.id, refetch]);
  if (!data?.items.length) return null;
  const children = data.items.map((item, index) => {
    if (item.type === "text") return <span key={index}>{item.text}</span>;
    if (item.type === "icon")
      return (
        <PluginIcon
          key={index}
          name={item.name}
          size={14}
        />
      );
    const query = new URLSearchParams({
      path: item.path,
      version: plugin.version,
      revision: String(plugin.reload_revision ?? 0),
    });
    return (
      <img
        key={index}
        className="app-status-bar__plugin-icon"
        src={`${getApiBaseUrl()}/plugins/${encodeURIComponent(plugin.id)}/status-icon?${query}`}
        alt=""
      />
    );
  });
  if (view.presentation === "none")
    return (
      <span
        className="app-status-bar__plugin-item"
        title={view.title}
      >
        {children}
      </span>
    );
  return (
    <EditorPluginOverlayButton
      plugin={plugin}
      view={view}
      context={context}
      side="top"
      trigger={
        <button
          type="button"
          className="app-status-bar__plugin-item"
          aria-label={view.title}
        >
          {children}
        </button>
      }
    />
  );
}
