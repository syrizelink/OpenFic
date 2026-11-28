import { Dialog, IconButton, Popover } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { pluginsQueryOptions, type InstalledPlugin, type PluginView } from "./api";
import { PluginFrame } from "./plugin-page";

interface Anchor {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface ActiveOverlay {
  view: PluginView;
  anchor?: Anchor;
  context: Record<string, unknown>;
}

export function PluginOverlays() {
  const { data: plugins = [] } = useQuery(pluginsQueryOptions);
  return (
    <div
      className="plugin-overlays"
      data-plugin-slot="app.overlay"
    >
      {plugins
        .filter((plugin) => plugin.status === "enabled")
        .map((plugin) => (
          <OverlayOwner
            key={`${plugin.id}:${plugin.version}:${plugin.reload_revision ?? 0}`}
            plugin={plugin}
          />
        ))}
    </div>
  );
}

function OverlayOwner({ plugin }: { plugin: InstalledPlugin }) {
  const [active, setActive] = useState<ActiveOverlay | null>(null);
  const close = useCallback(() => setActive(null), []);
  const request = useCallback(
    (method: string, params: Record<string, unknown>, context: Record<string, unknown>) => {
      if (method === "ui.closeOverlay") {
        close();
        return;
      }
      if (method !== "ui.openOverlay" || typeof params.viewId !== "string")
        throw new Error("Invalid overlay request");
      const target = plugin.views.find(
        (entry) =>
          entry.id === params.viewId &&
          entry.slot === "app.overlay" &&
          (entry.presentation === "dialog" || entry.presentation === "popover"),
      );
      if (!target) throw new Error("Overlay view not found in this plugin");
      let anchor: Anchor | undefined;
      if (params.anchor !== undefined) {
        const value = params.anchor;
        if (!value || typeof value !== "object" || Array.isArray(value))
          throw new Error("Invalid overlay anchor");
        const { x, y, width, height } = value as Record<string, unknown>;
        if (
          typeof x !== "number" ||
          typeof y !== "number" ||
          typeof width !== "number" ||
          typeof height !== "number" ||
          ![x, y, width, height].every(Number.isFinite) ||
          width < 0 ||
          height < 0
        )
          throw new Error("Overlay anchor requires finite coordinates and non-negative dimensions");
        const left = Math.max(0, Math.min(window.innerWidth, x));
        const top = Math.max(0, Math.min(window.innerHeight, y));
        anchor = {
          x: left,
          y: top,
          width: Math.min(width, window.innerWidth - left),
          height: Math.min(height, window.innerHeight - top),
        };
      }
      if (target.presentation === "popover" && !anchor)
        throw new Error("Popover requires an anchor");
      setActive({ view: target, anchor, context });
    },
    [plugin, close],
  );
  useEffect(() => {
    function handleRequest(event: Event) {
      const detail = (
        event as CustomEvent<{
          pluginId: string;
          method: string;
          params: Record<string, unknown>;
          context: Record<string, unknown>;
          error?: unknown;
          handled: boolean;
        }>
      ).detail;
      if (detail.pluginId !== plugin.id) return;
      detail.handled = true;
      try {
        request(detail.method, detail.params, detail.context);
      } catch (error) {
        detail.error = error;
      }
    }
    window.addEventListener("openfic:plugin-overlay", handleRequest);
    return () => window.removeEventListener("openfic:plugin-overlay", handleRequest);
  }, [plugin.id, request]);
  const current =
    active &&
    plugin.views.find(
      (entry) =>
        entry.id === active.view.id &&
        entry.slot === "app.overlay" &&
        entry.presentation === active.view.presentation,
    );
  return (
    <>
      {plugin.views
        .filter((view) => view.slot === "app.overlay" && !view.presentation)
        .map((view) => (
          <PluginFrame
            key={view.id}
            plugin={plugin}
            view={view}
            embedded
          />
        ))}
      {active && current && (
        <OverlayContent
          key={current.id}
          plugin={plugin}
          view={current}
          anchor={active.anchor}
          context={active.context}
          onClose={close}
        />
      )}
    </>
  );
}

function OverlayContent({
  plugin,
  view,
  anchor,
  context,
  onClose,
}: {
  plugin: InstalledPlugin;
  view: PluginView;
  anchor?: Anchor;
  context: Record<string, unknown>;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [height, setHeight] = useState(view.height ?? 320);
  const dialog = view.presentation === "dialog";
  const content = (
    <>
      <div className="editor-plugin-overlay-scroll">
        <div
          className="editor-plugin-overlay-body"
          style={view.renderer === "declarative" ? undefined : { height }}
        >
          <PluginFrame
            plugin={plugin}
            view={view}
            context={context}
            embedded
            onHeightChange={setHeight}
            onRequestClose={onClose}
          />
        </div>
      </div>
      {view.showCloseButton !== false && (
        <IconButton
          className="editor-plugin-overlay-close"
          size="1"
          variant="ghost"
          color="gray"
          aria-label={`${t("common.close")} ${view.title}`}
          onClick={onClose}
        >
          <X
            size={18}
            aria-hidden="true"
          />
        </IconButton>
      )}
    </>
  );
  if (dialog)
    return (
      <Dialog.Root
        open
        onOpenChange={(open) => {
          if (!open) onClose();
        }}
      >
        <Dialog.Content
          className="editor-plugin-overlay"
          aria-describedby={undefined}
          maxWidth="min(640px, calc(100vw - 24px))"
          maxHeight="calc(100dvh - 56px)"
        >
          <Dialog.Title className="editor-plugin-overlay-title">{view.title}</Dialog.Title>
          {content}
        </Dialog.Content>
      </Dialog.Root>
    );
  if (!anchor) return null;
  return (
    <Popover.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Popover.Anchor
        className="plugin-overlay-anchor"
        style={{ left: anchor.x, top: anchor.y, width: anchor.width, height: anchor.height }}
      />
      <Popover.Content
        className="editor-plugin-overlay"
        aria-label={view.title}
        side={context.slot === "editor.toolbar" ? "bottom" : "top"}
        align="end"
        collisionPadding={12}
        width="380px"
        maxWidth="min(calc(100vw - 24px), var(--radix-popover-content-available-width))"
        maxHeight="min(calc(100dvh - 56px), var(--radix-popover-content-available-height))"
      >
        {content}
      </Popover.Content>
    </Popover.Root>
  );
}
