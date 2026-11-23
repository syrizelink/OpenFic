import { IconButton, Tooltip, useThemeContext } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { toast } from "@/components";
import type { EditorToolbarPlacement } from "@/components/editor-toolbar";
import { Spinner } from "@/components/spinner";
import { apiClient } from "@/lib/api-client";

import { pluginError, pluginsQueryOptions, type InstalledPlugin, type PluginView } from "./api";
import { runUIEffects } from "./declarative-effects";
import { frontendCall } from "./frontend-host";
import { PluginIcon } from "./plugin-icon";

import "./plugins.css";

export function EditorPluginActions({
  context,
  placement,
}: {
  context: Record<string, unknown>;
  placement: EditorToolbarPlacement;
}) {
  const { data: plugins = [] } = useQuery(pluginsQueryOptions);
  const entries = plugins
    .filter((plugin) => plugin.status === "enabled")
    .flatMap((plugin) =>
      plugin.views
        .filter(
          (view) => view.slot === "editor.toolbar" && (view.placement ?? "right-end") === placement,
        )
        .map((view) => ({ plugin, view })),
    );
  if (!entries.length) return null;
  return (
    <div
      className="editor-plugin-actions"
      data-plugin-slot="editor.toolbar"
      data-placement={placement}
    >
      {entries.map(({ plugin, view }) => (
        <EditorPluginCommandButton
          key={`${plugin.id}:${plugin.version}:${view.id}:${JSON.stringify(context)}`}
          plugin={plugin}
          view={view}
          context={context}
        />
      ))}
    </div>
  );
}

export function EditorPluginCommandButton({
  plugin,
  view,
  context,
  children,
}: {
  plugin: InstalledPlugin;
  view: PluginView;
  context: Record<string, unknown>;
  children?: React.ReactNode;
}) {
  const { i18n } = useTranslation();
  const { appearance } = useThemeContext();
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const running = useRef<AbortController | null>(null);
  useEffect(() => () => running.current?.abort(), []);

  async function handleClick(event: React.MouseEvent<HTMLButtonElement>) {
    if (running.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const { signal } = (running.current = new AbortController());
    setPending(true);
    const actionContext = {
      ...context,
      pluginId: plugin.id,
      language: i18n.language,
      theme: appearance === "dark" ? "dark" : "light",
      settings: plugin.configuration,
      capabilities: plugin.capabilities,
      slot: view.slot,
      sdkVersion: "2.0.0",
      anchor: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
    };
    async function send(id: string, value: unknown, actionEvent: "press" | "change") {
      const { data } = await apiClient.post<{ result: unknown }>(
        `/plugins/${encodeURIComponent(plugin.id)}/views/${encodeURIComponent(view.id)}/action`,
        { id, value, event: actionEvent, context: actionContext },
        { signal },
      );
      return data.result;
    }
    try {
      const result = await send(view.id, null, "press");
      await runUIEffects(
        result,
        (method, params) =>
          frontendCall(
            method,
            params,
            plugin.capabilities,
            navigate,
            plugin.id,
            undefined,
            undefined,
            actionContext,
          ),
        (next, values) => send(next, values, "change"),
        () => !signal.aborted,
      );
    } catch (error) {
      if (!signal.aborted) toast.error(pluginError(error));
    } finally {
      running.current = null;
      if (!signal.aborted) setPending(false);
    }
  }

  if (children)
    return (
      <button
        type="button"
        className="app-status-bar__plugin-item"
        aria-label={view.title}
        disabled={pending}
        onClick={(event) => void handleClick(event)}
      >
        {children}
      </button>
    );
  return (
    <Tooltip content={view.title}>
      <IconButton
        type="button"
        className="editor-toolbar-button"
        variant="ghost"
        color="gray"
        highContrast
        size="2"
        aria-label={view.title}
        aria-busy={pending || undefined}
        disabled={pending}
        data-editor-plugin-action={`${plugin.id}/${view.id}`}
        onMouseDown={(event) => event.preventDefault()}
        onClick={(event) => void handleClick(event)}
      >
        {pending ? <Spinner size={18} /> : <PluginIcon name={view.icon ?? undefined} />}
      </IconButton>
    </Tooltip>
  );
}
