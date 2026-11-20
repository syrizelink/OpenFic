import { Dialog, IconButton, Popover, Tooltip, useThemeContext } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
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
import { diagnosticCall } from "./plugin-diagnostics";
import { PluginIcon } from "./plugin-icon";
import { PluginFrame } from "./plugin-page";

import "./plugins.css";

/** Editor slots contribute compact controls without embedding content in the toolbar. */
export function EditorPluginActions({
  context,
  placement,
}: {
  context: Record<string, unknown>;
  placement: EditorToolbarPlacement;
}) {
  const { data: plugins = [] } = useQuery(pluginsQueryOptions);
  const entries = plugins
    .filter((p) => p.status === "enabled")
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
        <EditorPluginAction
          key={`${plugin.id}:${plugin.version}:${view.id}:${JSON.stringify(context)}`}
          plugin={plugin}
          view={view}
          context={context}
        />
      ))}
    </div>
  );
}

interface EditorPluginActionProps {
  plugin: InstalledPlugin;
  view: PluginView;
  context: Record<string, unknown>;
}

function EditorPluginAction(props: EditorPluginActionProps) {
  return props.view.presentation === "action" ? (
    <EditorPluginCommandButton {...props} />
  ) : (
    <EditorPluginOverlayButton {...props} />
  );
}

export function EditorPluginCommandButton({ plugin, view, context }: EditorPluginActionProps) {
  const { i18n } = useTranslation();
  const { appearance } = useThemeContext();
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const running = useRef<AbortController | null>(null);
  useEffect(() => () => running.current?.abort(), []);

  async function handleClick() {
    if (running.current) return;
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
    };
    async function send(id: string, value: unknown, event: "press" | "change") {
      const { data } = await apiClient.post<{ result: unknown }>(
        `/plugins/${plugin.id}/views/${view.id}/action`,
        { id, value, event, context: actionContext },
        { signal },
      );
      return data.result;
    }
    try {
      const result = await diagnosticCall(
        plugin.id,
        "action",
        view.id,
        { event: "press" },
        () => send(view.id, null, "press"),
        view.id,
      );
      await runUIEffects(
        result,
        (method, params) =>
          diagnosticCall(
            plugin.id,
            "effect",
            method,
            params,
            () => frontendCall(method, params, plugin.capabilities, navigate),
            view.id,
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
        onClick={() => void handleClick()}
      >
        {pending ? <Spinner size={18} /> : <PluginIcon name={view.icon ?? undefined} />}
      </IconButton>
    </Tooltip>
  );
}

function EditorPluginOverlayButton({ plugin, view, context }: EditorPluginActionProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [tooltipOpen, setTooltipOpen] = useState(false);
  const restoringFocus = useRef(false);
  const [height, setHeight] = useState(view.height ?? 320);
  const dialog = view.presentation === "dialog";
  const Root = dialog ? Dialog.Root : Popover.Root;
  const Trigger = dialog ? Dialog.Trigger : Popover.Trigger;
  const Close = dialog ? Dialog.Close : Popover.Close;
  const label = `${t("common.close")} ${view.title}`;

  function handleOpenChange(next: boolean) {
    setTooltipOpen(false);
    setOpen(next);
  }

  function handleCloseAutoFocus() {
    // Radix restores focus synchronously after this callback.
    restoringFocus.current = true;
    queueMicrotask(() => {
      restoringFocus.current = false;
    });
  }

  const closeButton = view.showCloseButton !== false && (
    <Close>
      <IconButton
        className="editor-plugin-overlay-close"
        size="1"
        variant="ghost"
        color="gray"
        aria-label={label}
      >
        <X
          size={18}
          aria-hidden="true"
        />
      </IconButton>
    </Close>
  );
  const body = (
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
        onRequestClose={() => handleOpenChange(false)}
      />
    </div>
  );
  const content = (
    <>
      <div className="editor-plugin-overlay-scroll">{body}</div>
      {closeButton}
    </>
  );
  return (
    <Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Tooltip
        content={view.title}
        open={!open && tooltipOpen}
        onOpenChange={(next) => setTooltipOpen(next && !open && !restoringFocus.current)}
      >
        <Trigger>
          <IconButton
            type="button"
            className="editor-toolbar-button"
            variant="ghost"
            color="gray"
            highContrast
            size="2"
            aria-label={view.title}
            data-editor-plugin-action={`${plugin.id}/${view.id}`}
            onMouseDown={(event) => event.preventDefault()}
          >
            <PluginIcon name={view.icon ?? undefined} />
          </IconButton>
        </Trigger>
      </Tooltip>
      {dialog ? (
        <Dialog.Content
          className="editor-plugin-overlay"
          aria-describedby={undefined}
          maxWidth="min(640px, calc(100vw - 24px))"
          maxHeight="calc(100dvh - 56px)"
          onCloseAutoFocus={handleCloseAutoFocus}
        >
          <Dialog.Title className="editor-plugin-overlay-title">{view.title}</Dialog.Title>
          {content}
        </Dialog.Content>
      ) : (
        <Popover.Content
          className="editor-plugin-overlay"
          aria-label={view.title}
          side="bottom"
          align="end"
          collisionPadding={12}
          width="380px"
          maxWidth="min(calc(100vw - 24px), var(--radix-popover-content-available-width))"
          maxHeight="min(calc(100dvh - 56px), var(--radix-popover-content-available-height))"
          onCloseAutoFocus={handleCloseAutoFocus}
        >
          {content}
        </Popover.Content>
      )}
    </Root>
  );
}
