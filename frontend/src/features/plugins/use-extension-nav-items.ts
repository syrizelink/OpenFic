import { useQuery } from "@tanstack/react-query";
import { useLocation, useParams } from "react-router";

import { getApiBaseUrl } from "@/lib/api-client";

import { pluginsQueryOptions } from "./api";

export function useExtensionNavItems() {
  const { projectId } = useParams();
  const location = useLocation();
  const { data: plugins = [] } = useQuery(pluginsQueryOptions);
  return plugins
    .filter((plugin) => plugin.status === "enabled")
    .flatMap((plugin) =>
      plugin.views
        .filter((view) => view.slot === "sidebar.extensions")
        .map((view) => {
          const path = `/extensions/${plugin.id}/${view.id}`;
          const icon =
            view.icon || plugin.icon
              ? `${getApiBaseUrl()}/plugins/${encodeURIComponent(plugin.id)}/icon?${new URLSearchParams(
                  {
                    view_id: view.id,
                    view_icon: view.icon ?? "",
                    plugin_icon: plugin.icon ?? "",
                    version: plugin.version,
                    revision: String(plugin.development_revision ?? 0),
                    reload: String(plugin.reload_revision ?? 0),
                  },
                )}`
              : undefined;
          return {
            label: view.title,
            active: location.pathname === path,
            href: `${path}${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`,
            icon,
          };
        }),
    );
}
