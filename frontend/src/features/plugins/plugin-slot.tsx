import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { fetchPlugins, PLUGINS_QUERY_KEY } from "./api";
import { PluginFrame } from "./plugin-page";

export function PluginSlot({
  slot,
  context = {},
  inline = false,
}: {
  slot: string;
  context?: Record<string, unknown>;
  inline?: boolean;
}) {
  const { data: plugins = [] } = useQuery({
    queryKey: PLUGINS_QUERY_KEY,
    queryFn: fetchPlugins,
    refetchInterval: 5000,
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [heights, setHeights] = useState<Record<string, number>>({});
  const entries = plugins
    .filter((p) => p.status === "enabled")
    .flatMap((plugin) =>
      plugin.views.filter((view) => view.slot === slot).map((view) => ({ plugin, view })),
    );
  if (!entries.length) return null;
  return (
    <div
      className={`plugin-slot plugin-slot-${slot.replaceAll(".", "-")}`}
      data-plugin-slot={slot}
    >
      {entries.map(({ plugin, view }) => {
        const id = `${plugin.id}/${view.id}`;
        const open = inline || selected === id;
        const compact = plugin.format === "claude-mod" && slot === "assistant.above-prompt";
        const height = heights[id] ?? (compact ? 0 : (view.height ?? 320));
        return (
          <div
            key={id}
            className={`${open ? "plugin-slot-open" : ""}${compact ? " plugin-slot-compact" : ""}`}
          >
            {!inline && (
              <button
                type="button"
                onClick={() => setSelected(open ? null : id)}
                aria-expanded={open}
              >
                {view.title}
              </button>
            )}
            {open && (
              <div
                className="plugin-slot-content"
                style={{ height }}
              >
                <PluginFrame
                  key={`${id}:${plugin.version}`}
                  plugin={plugin}
                  view={view}
                  context={context}
                  embedded
                  onHeightChange={(next) =>
                    setHeights((current) =>
                      current[id] === next ? current : { ...current, [id]: next },
                    )
                  }
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
