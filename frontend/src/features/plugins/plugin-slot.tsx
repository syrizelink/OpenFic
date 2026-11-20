import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { pluginsQueryOptions } from "./api";
import { PluginFrame } from "./plugin-page";

export function PluginSlot({
  slot,
  context = {},
}: {
  slot: string;
  context?: Record<string, unknown>;
}) {
  const { data: plugins = [] } = useQuery(pluginsQueryOptions);
  const [selected, setSelected] = useState<string | null>(null);
  const [heights, setHeights] = useState<Record<string, number>>({});
  const entries = plugins
    .filter((p) => p.status === "enabled")
    .flatMap((plugin) =>
      plugin.views.filter((view) => view.slot === slot).map((view) => ({ plugin, view })),
    );
  // These slots are mounted only through EditorPluginActions inside the toolbar.
  if (slot === "editor.toolbar" || !entries.length) return null;
  return (
    <div
      className={`plugin-slot plugin-slot-${slot.replaceAll(".", "-")}`}
      data-plugin-slot={slot}
    >
      {entries.map(({ plugin, view }) => {
        const id = `${plugin.id}/${view.id}`;
        const open = selected === id;
        const native = view.renderer === "declarative";
        const height = heights[id] ?? view.height ?? 320;
        return (
          <div
            key={id}
            className={open ? "plugin-slot-open" : ""}
          >
            <button
              type="button"
              onClick={() => setSelected(open ? null : id)}
              aria-expanded={open}
            >
              {view.title}
            </button>
            {open && (
              <div
                className="plugin-slot-content"
                style={native ? undefined : { height }}
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
