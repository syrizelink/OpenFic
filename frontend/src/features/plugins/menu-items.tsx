import { useQuery } from "@tanstack/react-query";
import type { LucideProps } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { toast } from "@/components";
import type { ContextMenuItem } from "@/components/context-menu";
import { apiClient } from "@/lib/api-client";

import { pluginError, pluginsQueryOptions } from "./api";
import { runUIEffects } from "./declarative-effects";
import { frontendCall } from "./frontend-host";
import { PluginIcon } from "./plugin-icon";

export interface PluginMenuTarget {
  kind:
    | "menu.character"
    | "menu.chapter"
    | "menu.volume"
    | "menu.note"
    | "menu.note-category"
    | "menu.world-info-entry";
  ids: string[];
  projectId: string | null;
}

export function usePluginMenuItems(target: PluginMenuTarget | null): ContextMenuItem[] {
  const { data: plugins = [] } = useQuery(pluginsQueryOptions);
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  if (!target || target.ids.length === 0) return [];

  return plugins
    .filter((plugin) => plugin.status === "enabled" && plugin.capabilities.includes("ui"))
    .flatMap((plugin) =>
      plugin.views
        .filter((view) => view.slot === target.kind && view.presentation === "action")
        .map((view) => ({
          id: `${plugin.id}:${view.id}`,
          label: view.title,
          ...(view.icon
            ? {
                icon: (props: LucideProps) => (
                  <PluginIcon
                    {...props}
                    name={view.icon ?? undefined}
                  />
                ),
              }
            : {}),
          onClick: (anchor) => {
            const context = {
              projectId: target.projectId,
              pluginId: plugin.id,
              language: i18n.language,
              settings: plugin.configuration,
              capabilities: plugin.capabilities,
              slot: view.slot,
              sdkVersion: "2.0.0",
              menuTarget: target,
              anchor,
            };
            async function send(id: string, value: unknown, event: "press" | "change") {
              const { data } = await apiClient.post<{ result: unknown }>(
                `/plugins/${encodeURIComponent(plugin.id)}/views/${encodeURIComponent(view.id)}/action`,
                { id, value, event, context },
              );
              return data.result;
            }
            void send(view.id, target, "press")
              .then((result) =>
                runUIEffects(
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
                      context,
                    ),
                  (id, values) => send(id, values, "change"),
                  () => true,
                ),
              )
              .catch((error: unknown) => toast.error(pluginError(error)));
          },
        })),
    );
}
