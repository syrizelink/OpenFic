import { Button, Flex, Heading, Text, useThemeContext } from "@radix-ui/themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router";

import { PortalContainerContext } from "@/components/portal-container";
import { Spinner } from "@/components/spinner";
import { apiClient } from "@/lib/api-client";
import { getSocketConnectionStatus } from "@/lib/socket-client";

import { pluginError, type InstalledPlugin, type PluginView } from "./api";
import { scopeCSS } from "./declarative-css";
import { runUIEffects } from "./declarative-effects";
import { useDeclarativeLocalState } from "./declarative-local-state";
import { type UIDocument, type UIAction } from "./declarative-schema";
import { DeclarativeErrorBoundary, renderTree } from "./declarative-tree";
import { frontendCall } from "./frontend-host";
import { shouldRefreshPluginView } from "./plugin-refresh";

function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

export function DeclarativeView({
  plugin,
  view,
  context = {},
  embedded = false,
  fullPage = false,
  onRequestClose,
}: {
  plugin: InstalledPlugin;
  view: PluginView;
  context?: Record<string, unknown>;
  embedded?: boolean;
  fullPage?: boolean;
  onRequestClose?: () => void;
}) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const { appearance } = useThemeContext();
  const params = useParams();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const projectId = context.projectId ?? params.projectId ?? search.get("projectId");
  const contextKey = JSON.stringify({
    ...context,
    pluginId: plugin.id,
    projectId,
    language: i18n.language,
    theme: appearance === "dark" ? "dark" : "light",
    settings: plugin.configuration,
    capabilities: plugin.capabilities,
    slot: view.slot,
    sdkVersion: "2.0.0",
  });
  const root = useRef<HTMLDivElement>(null);
  const scope = "plugin-ui-" + useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const [portal, setPortal] = useState<HTMLElement | null>(null);
  useEffect(() => {
    const container = document.createElement("div");
    container.dataset.pluginStyleRoot = scope;
    container.dataset.pluginPortal = plugin.id + "/" + view.id;
    container.style.setProperty("display", "contents", "important");
    const parent = view.slot === "settings" ? root.current?.closest(".settings-plugin-page") : null;
    (parent ?? document.body).appendChild(container);
    setPortal(container);
    return () => container.remove();
  }, [scope, plugin.id, view.id, view.slot]);
  const [columns, setColumns] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const queue = useRef<Promise<void>>(Promise.resolve());
  const generation = useRef({ active: true, pending: 0 });
  const paneKey = useRef("");
  const renderKey = [
    "plugin-declarative",
    plugin.id,
    plugin.version,
    plugin.reload_revision,
    view.id,
    contextKey,
  ] as const;
  const {
    data,
    error: renderError,
    refetch,
  } = useQuery<UIDocument>({
    queryKey: [...renderKey, columns],
    enabled: columns !== null,
    placeholderData: (previous, previousQuery) =>
      renderKey.every((part, index) => part === previousQuery?.queryKey[index])
        ? previous
        : undefined,
    queryFn: async ({ signal }) =>
      (
        await apiClient.post<UIDocument>(
          `/plugins/${plugin.id}/views/${view.id}/render`,
          { context: JSON.parse(contextKey), columns },
          { signal },
        )
      ).data,
    refetchOnWindowFocus: false,
  });
  const styles = useMemo(() => scopeCSS(data?.css ?? "", scope), [data?.css, scope]);
  const local = useDeclarativeLocalState(
    plugin.id,
    view.id,
    data?.state ?? {},
    data?.localActions ?? {},
  );
  const actions = useRef<UIAction>(() => {});
  const run: UIAction = (id, value = null, event = "press") => {
    if (!id) return;
    const current = generation.current;
    if (current.pending >= 32) {
      setError("Too many pending UI actions");
      return;
    }
    current.pending++;
    setError(null);
    queue.current = queue.current
      .then(async () => {
        if (!current.active) return;
        const send = async (actionId: string, actionValue: unknown, actionEvent: string) =>
          (
            await apiClient.post<{ result: unknown }>(
              `/plugins/${plugin.id}/views/${view.id}/action`,
              {
                id: actionId,
                value: actionValue,
                event: actionEvent,
                context: JSON.parse(contextKey),
              },
            )
          ).data.result;
        const response = await send(id, value, event);
        const result = await runUIEffects(
          response,
          (method, args) =>
            frontendCall(
              method,
              args,
              plugin.capabilities,
              navigate,
              plugin.id,
              onRequestClose &&
                (() => {
                  current.active = false;
                  onRequestClose();
                }),
              undefined,
              JSON.parse(contextKey),
            ),
          (next, values) => send(next, values, "change"),
          () => current.active,
        );
        if (current.active && event === "command") {
          setMessage(
            result && typeof result === "object" && "text" in result ? str(result.text) : "",
          );
        }
        if (current.active && getSocketConnectionStatus() !== "connected") await refetch();
      })
      .catch((fault: unknown) => {
        if (current.active) setError(pluginError(fault));
      })
      .finally(() => {
        current.pending--;
      });
  };
  const dispatch: UIAction = (id, value = null, event = "press") => {
    if (id.startsWith("local.")) local.apply(id, value);
    else run(id, value, event);
  };
  useEffect(() => {
    actions.current = dispatch;
  });
  useEffect(() => {
    const lifetime = { active: true, pending: 0 };
    generation.current = lifetime;
    setError(null);
    setMessage("");
    return () => {
      lifetime.active = false;
    };
  }, [contextKey, plugin.id, view.id]);
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const measure = () => {
      const next = Math.max(20, Math.min(240, Math.floor(element.clientWidth / 7.2)));
      setColumns(next);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let refreshView = false;
    const invalidate = (event: Event) => {
      const detail = (
        event as CustomEvent<{
          event: string;
          pluginId?: string;
          data?: { viewId?: string; resync?: boolean };
        }>
      ).detail;
      if (detail.event !== "ui.invalidate" && detail.event !== "data.changed") return;
      const shouldRefresh = shouldRefreshPluginView(
        detail,
        plugin.id,
        view.id,
        plugin.capabilities,
      );
      if (!shouldRefresh && detail.event !== "data.changed") return;
      refreshView ||= shouldRefresh;
      clearTimeout(timer);
      timer = setTimeout(() => {
        void queryClient.invalidateQueries({
          queryKey: ["plugin-component-data", plugin.id, view.id],
        });
        if (refreshView) void refetch();
        refreshView = false;
      }, 50);
    };
    window.addEventListener("openfic:plugin-event", invalidate);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("openfic:plugin-event", invalidate);
    };
  }, [refetch, queryClient, plugin.id, plugin.capabilities, view.id]);
  useEffect(() => {
    const next = data?.panes.map((pane) => pane.id).join("/") ?? "";
    if (next && next !== paneKey.current && data?.panes.some((pane) => pane.focus)) {
      (
        root.current?.querySelector<HTMLElement>('[data-plugin-autofocus="true"]') ??
        portal?.querySelector<HTMLElement>('[data-plugin-autofocus="true"]')
      )?.focus();
    } else if (!next && paneKey.current) {
      root.current?.querySelector<HTMLElement>("button")?.focus();
    }
    paneKey.current = next;
  }, [data, portal]);
  const trees = data?.trees.filter((entry) => entry.tree != null) ?? [];
  return (
    <PortalContainerContext.Provider value={portal ?? undefined}>
      <div
        ref={root}
        className={`plugin-declarative${embedded ? " plugin-declarative-embedded" : ""}`}
        data-plugin-view={`${plugin.id}/${view.id}`}
        data-renderer="declarative"
        data-plugin-style-root={scope}
        data-empty={String(!trees.length && !error && !renderError)}
        aria-label={view.title}
        onKeyDown={(event) => {
          if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
          if (
            (event.target as HTMLElement).closest('[role="dialog"],[role="menu"],[role="listbox"]')
          )
            return;
          const pane = data?.panes.find((item) => item.closeOnEscape);
          if (event.key === "Escape" && pane) {
            event.preventDefault();
            event.stopPropagation();
            actions.current(pane.id, null, "close");
            return;
          }
          if (
            (event.target as HTMLElement).closest(
              'input,textarea,[contenteditable="true"],[role="combobox"],[role="switch"],[role="checkbox"]',
            )
          )
            return;
          const button = [
            ...(root.current?.querySelectorAll<HTMLButtonElement>("button[data-hotkey]") ?? []),
            ...(portal?.querySelectorAll<HTMLButtonElement>("button[data-hotkey]") ?? []),
          ].find((item) => item.dataset.hotkey?.toLowerCase() === event.key.toLowerCase());
          if (button && !button.disabled) {
            event.preventDefault();
            event.stopPropagation();
            button.click();
          }
        }}
      >
        <style>{styles.css}</style>
        {!embedded && !fullPage && (
          <Flex
            direction="column"
            gap="2"
            mb="3"
          >
            <Heading
              as="h2"
              size="4"
              weight="bold"
            >
              {view.title}
            </Heading>
            <Flex
              gap="2"
              wrap="wrap"
            >
              {data?.commands.map((command) => (
                <Button
                  key={command.name}
                  size="1"
                  variant="soft"
                  onClick={() => dispatch(command.name, "", "command")}
                >
                  /{command.name}
                </Button>
              ))}
            </Flex>
          </Flex>
        )}
        {!data &&
          !renderError &&
          !embedded &&
          (fullPage ? (
            <div className="plugin-page-loading">
              <Spinner aria-label={t("plugins.loading")} />
            </div>
          ) : (
            <Spinner />
          ))}
        {message && (
          <Text
            as="p"
            role="status"
          >
            {message}
          </Text>
        )}
        {(error || renderError) && (
          <Text
            as="p"
            role="alert"
            color="red"
          >
            {error ?? pluginError(renderError)}
          </Text>
        )}
        {!fullPage && styles.warnings.length > 0 && (
          <Text
            role="status"
            size="1"
            color="gray"
          >
            {styles.warnings.join(" ")}
          </Text>
        )}
        {portal && (
          <DeclarativeErrorBoundary resetKey={data}>
            {trees.map((entry, index) => (
              <section
                key={`${entry.component}:${entry.requestId}:${index}`}
                data-component={entry.component}
                role={entry.component === "Pane" ? "region" : undefined}
                aria-label={
                  entry.component === "Pane"
                    ? data?.panes.find((pane) => pane.id === entry.requestId)?.title || plugin.name
                    : undefined
                }
                aria-live={entry.component === "Pane" ? undefined : "polite"}
              >
                {renderTree(entry.tree, {
                  action: dispatch,
                  pluginId: plugin.id,
                  viewId: view.id,
                  localState: local.values,
                  localInitial: Object.fromEntries(
                    Object.entries(data?.state ?? {}).map(([name, definition]) => [
                      name,
                      definition.initial,
                    ]),
                  ),
                  portal,
                  animations: styles.animations,
                  animationVariables: styles.animationVariables,
                })}
              </section>
            ))}
          </DeclarativeErrorBoundary>
        )}
      </div>
    </PortalContainerContext.Provider>
  );
}
