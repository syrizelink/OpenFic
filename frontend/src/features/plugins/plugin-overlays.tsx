import { useQuery } from "@tanstack/react-query";

import { fetchPlugins, PLUGINS_QUERY_KEY } from "./api";
import { PluginFrame } from "./plugin-page";

/** Native overlay views reserve no layout space; only their content receives input. */
export function PluginOverlays() {
  const { data: plugins = [] } = useQuery({
    queryKey: PLUGINS_QUERY_KEY,
    queryFn: fetchPlugins,
    refetchInterval: 5000,
  });
  return (
    <div
      className="plugin-overlays"
      data-plugin-slot="app.overlay"
    >
      {plugins
        .filter((p) => p.status === "enabled")
        .flatMap((plugin) =>
          plugin.views
            .filter((view) => view.slot === "app.overlay")
            .map((view) => (
              <PluginFrame
                key={`${plugin.id}:${plugin.version}:${view.id}`}
                plugin={plugin}
                view={view}
                embedded
              />
            )),
        )}
    </div>
  );
}
