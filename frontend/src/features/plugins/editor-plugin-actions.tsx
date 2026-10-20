import { Dialog, Flex, IconButton, Popover, Text, Tooltip } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  EDITOR_PLUGIN_SLOTS,
  fetchPlugins,
  PLUGINS_QUERY_KEY,
  type InstalledPlugin,
  type PluginView,
} from "./api";
import { PluginIcon } from "./plugin-icon";
import { PluginFrame } from "./plugin-page";

import "./plugins.css";

/** Editor slots contribute only compact controls. Content always lives in a portal. */
export function EditorPluginActions({ context }: { context: Record<string, unknown> }) {
  const { data: plugins = [] } = useQuery({
    queryKey: PLUGINS_QUERY_KEY,
    queryFn: fetchPlugins,
    refetchInterval: 5000,
  });
  const entries = plugins
    .filter((p) => p.status === "enabled")
    .flatMap((plugin) =>
      plugin.views
        .filter((view) => EDITOR_PLUGIN_SLOTS.includes(view.slot))
        .map((view) => ({ plugin, view })),
    );
  if (!entries.length) return null;
  return (
    <div
      className="editor-plugin-actions"
      data-plugin-slot="editor.toolbar"
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

function EditorPluginAction({
  plugin,
  view,
  context,
}: {
  plugin: InstalledPlugin;
  view: PluginView;
  context: Record<string, unknown>;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [height, setHeight] = useState(view.height ?? 320);
  const dialog =
    (view.presentation ?? (view.slot === "editor.panel" ? "dialog" : "popover")) === "dialog";
  const Root = dialog ? Dialog.Root : Popover.Root;
  const Trigger = dialog ? Dialog.Trigger : Popover.Trigger;
  const Close = dialog ? Dialog.Close : Popover.Close;
  const label = `${t("common.close")} ${view.title}`;
  const header = (
    <Flex
      justify="between"
      align="center"
      gap="3"
      mb="3"
    >
      {dialog ? (
        <Dialog.Title
          mb="0"
          size="3"
        >
          {view.title}
        </Dialog.Title>
      ) : (
        <Text weight="medium">{view.title}</Text>
      )}
      <Close>
        <IconButton
          size="1"
          variant="ghost"
          color="gray"
          aria-label={label}
        >
          <X size={16} />
        </IconButton>
      </Close>
    </Flex>
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
      />
    </div>
  );
  return (
    <Root
      open={open}
      onOpenChange={setOpen}
    >
      <Tooltip content={view.title}>
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
          maxHeight="calc(100dvh - 32px)"
        >
          {header}
          {body}
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
          maxHeight="min(calc(100dvh - 32px), var(--radix-popover-content-available-height))"
        >
          {header}
          {body}
        </Popover.Content>
      )}
    </Root>
  );
}
