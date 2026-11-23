import { useQuery } from "@tanstack/react-query";
import type { LucideProps } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { ContextMenu, toast } from "@/components";
import type { ContextMenuItem } from "@/components/context-menu";
import { apiClient } from "@/lib/api-client";
import { writeClipboardText } from "@/lib/clipboard";

import { pluginError, pluginsQueryOptions, type InstalledPlugin, type PluginView } from "./api";
import { runUIEffects } from "./declarative-effects";
import { frontendCall } from "./frontend-host";
import { PluginIcon } from "./plugin-icon";
import { readSelection, type SelectionSnapshot } from "./selection";

interface SelectionMenuState {
  selection: SelectionSnapshot;
  position: { x: number; y: number };
  trigger: "selection" | "contextmenu";
  entries: { plugin: InstalledPlugin; view: PluginView }[];
}

function matchingEntries(
  plugins: InstalledPlugin[],
  selection: SelectionSnapshot,
  trigger: "selection" | "contextmenu",
) {
  return plugins
    .filter(
      (plugin) => plugin.status === "enabled" && plugin.capabilities.includes("selection.read"),
    )
    .flatMap((plugin) =>
      plugin.views
        .filter(
          (view) =>
            view.slot === "menu.selection" &&
            view.selectionTriggers?.includes(trigger) &&
            view.selectionSources?.includes(selection.source.kind),
        )
        .map((view) => ({ plugin, view })),
    );
}

export function SelectionMenu() {
  const { data: plugins = [] } = useQuery(pluginsQueryOptions);
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const [menu, setMenu] = useState<SelectionMenuState | null>(null);
  const activeSelection = useRef<SelectionSnapshot | null>(null);

  useEffect(() => {
    let hasTouchPointer = false;
    let mouseSelectionStart:
      | {
          anchorNode: Node | null;
          anchorOffset: number;
          focusNode: Node | null;
          focusOffset: number;
        }
      | null
      | undefined;
    let mouseDownPosition: { x: number; y: number } | undefined;
    let shouldPreventMouseUp = false;
    function open(trigger: "selection" | "contextmenu", event: MouseEvent | KeyboardEvent) {
      const selection = readSelection();
      if (!selection) return;
      if (event instanceof MouseEvent) {
        const element = event.target instanceof Element ? event.target : null;
        const source = element?.closest<HTMLElement>("[data-plugin-selection-source]");
        if (
          !source ||
          source.dataset.pluginSelectionSource !== selection.source.kind ||
          (source.dataset.pluginSelectionId || undefined) !== selection.source.id
        )
          return;
        if (
          trigger === "contextmenu" &&
          element?.closest('[data-plugin-editor-context-menu="true"]')
        )
          return;
      }
      let entries = matchingEntries(plugins, selection, trigger);
      if (trigger === "contextmenu" && !entries.length) {
        const active = activeSelection.current;
        const isActiveSelection =
          active?.source.kind === selection.source.kind &&
          active.source.id === selection.source.id &&
          active.source.projectId === selection.source.projectId &&
          active.text === selection.text;
        const isTouch =
          hasTouchPointer ||
          (event instanceof PointerEvent && ["touch", "pen"].includes(event.pointerType));
        if (isTouch) entries = matchingEntries(plugins, selection, "selection");
        if (isActiveSelection || entries.length) {
          event.preventDefault();
          event.stopPropagation();
        }
        if (!entries.length) return;
      }
      if (!entries.length) return;
      if (trigger === "contextmenu") {
        event.preventDefault();
        event.stopPropagation();
      }
      const position =
        trigger === "contextmenu" && event instanceof MouseEvent
          ? { x: event.clientX, y: event.clientY }
          : {
              x: selection.bounds.x,
              y: ["chapter", "note", "character", "world-info", "agent-message"].includes(
                selection.source.kind,
              )
                ? selection.bounds.y
                : selection.bounds.y + selection.bounds.height,
            };
      activeSelection.current = selection;
      setMenu({ selection, position, entries, trigger });
      return selection;
    }
    const pointerDown = (event: PointerEvent) => {
      hasTouchPointer = ["touch", "pen"].includes(event.pointerType);
      shouldPreventMouseUp = false;
      if (event.pointerType !== "mouse" || event.button !== 0) {
        mouseSelectionStart = undefined;
        mouseDownPosition = undefined;
        return;
      }
      mouseDownPosition = { x: event.clientX, y: event.clientY };
      const selection = window.getSelection();
      mouseSelectionStart = selection
        ? {
            anchorNode: selection.anchorNode,
            anchorOffset: selection.anchorOffset,
            focusNode: selection.focusNode,
            focusOffset: selection.focusOffset,
          }
        : null;
    };
    const pointerUp = (event: PointerEvent) => {
      if (event.pointerType === "mouse" && event.button !== 0) return;
      if (event.pointerType !== "mouse") {
        open("selection", event);
        return;
      }
      if (mouseSelectionStart === undefined) return;
      const selection = window.getSelection();
      const isDrag =
        mouseDownPosition &&
        (Math.abs(event.clientX - mouseDownPosition.x) > 3 ||
          Math.abs(event.clientY - mouseDownPosition.y) > 3);
      const hasSelectionChanged = Boolean(
        selection &&
        (isDrag ||
          !mouseSelectionStart ||
          mouseSelectionStart.anchorNode !== selection.anchorNode ||
          mouseSelectionStart.anchorOffset !== selection.anchorOffset ||
          mouseSelectionStart.focusNode !== selection.focusNode ||
          mouseSelectionStart.focusOffset !== selection.focusOffset),
      );
      if (!hasSelectionChanged) return;
      shouldPreventMouseUp = Boolean(open("selection", event));
    };
    const pointerCancel = () => {
      hasTouchPointer = false;
      mouseSelectionStart = undefined;
      mouseDownPosition = undefined;
      shouldPreventMouseUp = false;
    };
    const mouseUp = (event: MouseEvent) => {
      if (event.button === 0 && shouldPreventMouseUp) event.preventDefault();
      mouseSelectionStart = undefined;
      mouseDownPosition = undefined;
      shouldPreventMouseUp = false;
    };
    const keyUp = (event: KeyboardEvent) => {
      if (
        event.shiftKey &&
        (event.key.startsWith("Arrow") || ["Home", "End", "PageUp", "PageDown"].includes(event.key))
      )
        open("selection", event);
    };
    const contextMenu = (event: MouseEvent) => open("contextmenu", event);
    document.addEventListener("pointerdown", pointerDown, true);
    const clearTouchPointer = () => {
      hasTouchPointer = false;
    };
    document.addEventListener("pointerup", clearTouchPointer, true);
    document.addEventListener("pointerup", pointerUp);
    document.addEventListener("pointercancel", pointerCancel, true);
    document.addEventListener("mouseup", mouseUp, true);
    document.addEventListener("keyup", keyUp);
    document.addEventListener("contextmenu", contextMenu, true);
    return () => {
      document.removeEventListener("pointerdown", pointerDown, true);
      document.removeEventListener("pointerup", clearTouchPointer, true);
      document.removeEventListener("pointerup", pointerUp);
      document.removeEventListener("pointercancel", pointerCancel, true);
      document.removeEventListener("mouseup", mouseUp, true);
      document.removeEventListener("keyup", keyUp);
      document.removeEventListener("contextmenu", contextMenu, true);
    };
  }, [plugins]);

  const run = useCallback(
    async (
      plugin: InstalledPlugin,
      view: PluginView,
      selection: SelectionSnapshot,
      anchor: { x: number; y: number; width: number; height: number },
    ) => {
      const context = {
        projectId: selection.source.projectId ?? selection.target?.projectId ?? null,
        pluginId: plugin.id,
        language: i18n.language,
        settings: plugin.configuration,
        capabilities: plugin.capabilities,
        slot: view.slot,
        sdkVersion: "2.0.0",
        selection,
        anchor,
      };
      async function send(id: string, value: unknown, event: "press" | "change") {
        const { data } = await apiClient.post<{ result: unknown }>(
          `/plugins/${encodeURIComponent(plugin.id)}/views/${encodeURIComponent(view.id)}/action`,
          { id, value, event, context },
        );
        return data.result;
      }
      try {
        const result = await send(view.id, selection, "press");
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
              selection,
              context,
            ),
          (id, values) => send(id, values, "change"),
          () => true,
        );
      } catch (error) {
        toast.error(pluginError(error));
      }
    },
    [i18n.language, navigate],
  );

  useEffect(() => {
    const listener = (event: Event) => {
      const detail = (
        event as CustomEvent<{ target: EventTarget | null; items: ContextMenuItem[] }>
      ).detail;
      const selection = readSelection();
      const source =
        detail.target instanceof Element
          ? detail.target.closest<HTMLElement>("[data-plugin-selection-source]")
          : null;
      if (
        !selection ||
        !source ||
        source.dataset.pluginSelectionSource !== selection.source.kind ||
        (source.dataset.pluginSelectionId || undefined) !== selection.source.id
      )
        return;
      for (const { plugin, view } of matchingEntries(plugins, selection, "contextmenu")) {
        detail.items.push({
          id: `${plugin.id}:${view.id}`,
          label: view.title,
          onClick: (anchor) => void run(plugin, view, selection, anchor),
        });
      }
    };
    window.addEventListener("openfic:editor-selection-menu", listener);
    return () => window.removeEventListener("openfic:editor-selection-menu", listener);
  }, [plugins, run]);

  const isEditorSelection =
    menu?.trigger === "selection" &&
    ["chapter", "note", "character", "world-info"].includes(menu.selection.source.kind);
  const isMessageSelection =
    menu?.trigger === "selection" && menu.selection.source.kind === "agent-message";
  const isHorizontalSelection = isEditorSelection || isMessageSelection;

  return (
    <ContextMenu
      position={menu?.position ?? null}
      orientation={isHorizontalSelection ? "horizontal" : "vertical"}
      side={isHorizontalSelection ? "top" : "bottom"}
      onClose={() => {
        activeSelection.current = null;
        setMenu(null);
      }}
      items={
        menu
          ? [
              ...menu.entries.map(({ plugin, view }) => ({
                id: `${plugin.id}:${view.id}`,
                label: view.title,
                ...(isHorizontalSelection && view.icon
                  ? {
                      iconOnly: isMessageSelection,
                      icon: (props: LucideProps) => (
                        <PluginIcon
                          {...props}
                          name={view.icon ?? undefined}
                        />
                      ),
                    }
                  : {}),
                onClick: (anchor: Parameters<ContextMenuItem["onClick"]>[0]) =>
                  void run(plugin, view, menu.selection, anchor),
              })),
              ...(menu.trigger === "contextmenu"
                ? [
                    {
                      id: "openfic:copy-selection",
                      label: i18n.t("editor.copy"),
                      onClick: () =>
                        void writeClipboardText(menu.selection.text)
                          .then((success) => {
                            if (!success) toast.error(i18n.t("editor.copyFailed"));
                          })
                          .catch(() => toast.error(i18n.t("editor.copyFailed"))),
                    },
                  ]
                : []),
            ]
          : []
      }
    />
  );
}
