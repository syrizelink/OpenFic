import { Button, Flex, useThemeContext } from "@radix-ui/themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useSearchParams, useNavigate } from "react-router";

import { Spinner } from "@/components/spinner";
import { useAppShell } from "@/features/app-shell/components/app-shell-context";
import { apiClient, resolveBackendUrl } from "@/lib/api-client";

import { pluginsQueryOptions, pluginError, type InstalledPlugin, type PluginView } from "./api";
import { DeclarativeView } from "./declarative-view";
import { frontendCall } from "./frontend-host";

import "./plugins.css";

export type OverlayRequest = (method: string, params: Record<string, unknown>) => void;

export function PluginPage() {
  const { openSettings } = useAppShell();
  const { pluginId, viewId } = useParams();
  const { t } = useTranslation();
  const { data: plugins, isLoading, error } = useQuery(pluginsQueryOptions);
  const plugin = plugins?.find((entry) => entry.id === pluginId && entry.status === "enabled");
  const view = plugin?.views.find((entry) => entry.id === viewId);
  if (isLoading)
    return (
      <div className="plugin-page">
        <div className="plugin-page-loading">
          <Spinner aria-label={t("plugins.loading")} />
        </div>
      </div>
    );
  if (!plugin || !view || view.presentation === "action" || error)
    return (
      <div className="extensions-page">
        <p role="alert">{error ? pluginError(error) : t("plugins.unavailable")}</p>
        <Button
          variant="soft"
          onClick={() => openSettings({ category: "plugins" })}
        >
          {t("plugins.management")}
        </Button>
      </div>
    );
  return (
    <div className="plugin-page">
      <PluginFrame
        key={`${plugin.id}:${plugin.version}:${view.id}:${JSON.stringify(plugin.configuration)}`}
        plugin={plugin}
        view={view}
        fullPage
      />
    </div>
  );
}

export function PluginFrame({
  plugin,
  view,
  context,
  embedded,
  fullPage,
  onHeightChange,
  onRequestClose,
  onOverlayRequest,
}: {
  plugin: InstalledPlugin;
  view: PluginView;
  context?: Record<string, unknown>;
  embedded?: boolean;
  fullPage?: boolean;
  onHeightChange?: (height: number) => void;
  onRequestClose?: () => void;
  onOverlayRequest?: OverlayRequest;
}) {
  if (view.renderer === "declarative")
    return (
      <DeclarativeView
        key={`${plugin.reload_revision ?? 0}`}
        plugin={plugin}
        view={view}
        context={context}
        embedded={embedded}
        fullPage={fullPage}
        onRequestClose={onRequestClose}
        onOverlayRequest={onOverlayRequest}
      />
    );
  return (
    <IframeView
      key={`${plugin.reload_revision ?? 0}`}
      plugin={plugin}
      view={view}
      context={context}
      embedded={embedded}
      fullPage={fullPage}
      onHeightChange={onHeightChange}
      onRequestClose={onRequestClose}
      onOverlayRequest={onOverlayRequest}
    />
  );
}

function IframeView({
  plugin,
  view,
  context = {},
  embedded = false,
  fullPage = false,
  onHeightChange,
  onRequestClose,
  onOverlayRequest,
}: {
  plugin: InstalledPlugin;
  view: PluginView;
  context?: Record<string, unknown>;
  embedded?: boolean;
  fullPage?: boolean;
  onHeightChange?: (height: number) => void;
  onRequestClose?: () => void;
  onOverlayRequest?: OverlayRequest;
}) {
  const { t, i18n } = useTranslation();
  const { openSettings } = useAppShell();
  const [search] = useSearchParams();
  const routeParams = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const frame = useRef<HTMLIFrameElement>(null);
  const heightChange = useRef(onHeightChange);
  const requestedHeight = useRef<number | null>(null);
  useEffect(() => {
    heightChange.current = onHeightChange;
  }, [onHeightChange]);
  const [channel] = useState(() => crypto.randomUUID());
  const [ready, setReady] = useState(false);
  const initialized = useRef(false);
  const [fault, setFault] = useState(false);
  const isOverlay = view.slot === "app.overlay" && !view.presentation;
  const [overlayBounds, setOverlayBounds] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const requestedBounds = useRef(overlayBounds);
  const language = i18n.language;
  const projectId = context.projectId ?? routeParams.projectId ?? search.get("projectId");
  const extraContext = JSON.stringify(context);
  const capabilityKey = plugin.capabilities.join(",");
  const configuration = JSON.stringify(plugin.configuration);
  const { appearance } = useThemeContext();
  const theme = context.theme === "dark" || appearance === "dark" ? "dark" : "light";
  useEffect(() => {
    let disposed = false;
    let inFlight = 0;
    const timer = window.setTimeout(() => setFault(true), 15000);
    const reply = (payload: Record<string, unknown>) =>
      frame.current?.contentWindow?.postMessage(
        { protocol: "openfic.plugin.v1", channel, ...payload },
        "*",
      );
    const resizeView = (height: number) => {
      const bounded = Math.max(0, Math.min(1600, Math.ceil(height)));
      if (isOverlay) {
        requestedBounds.current = { ...requestedBounds.current, height: bounded };
        return fitOverlay().height;
      } else heightChange.current?.(bounded);
      return bounded;
    };
    const fitOverlay = () => {
      const bounds = requestedBounds.current;
      const x = Math.max(0, Math.min(window.innerWidth, bounds.x));
      const y = Math.max(0, Math.min(window.innerHeight, bounds.y));
      const fitted = {
        x,
        y,
        width: Math.max(0, Math.min(window.innerWidth - x, bounds.width)),
        height: Math.max(0, Math.min(window.innerHeight - y, bounds.height)),
      };
      setOverlayBounds(fitted);
      return fitted;
    };
    const viewportResize = () => {
      if (isOverlay) fitOverlay();
      if (requestedHeight.current !== null) resizeView(requestedHeight.current);
      if (isOverlay)
        reply({
          type: "event",
          event: "ui.viewportChanged",
          data: { width: window.innerWidth, height: window.innerHeight },
        });
    };
    window.addEventListener("resize", viewportResize);
    const localEvent = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (
        detail.event === "ui.invalidate" &&
        ((detail.pluginId && detail.pluginId !== plugin.id) ||
          (detail.data?.viewId && detail.data.viewId !== view.id))
      )
        return;
      if (detail.event.startsWith("editor.") && !capabilityKey.split(",").includes("editor.read"))
        return;
      if (!detail.event.startsWith("editor.") && !capabilityKey.split(",").includes("events"))
        return;
      reply({ type: "event", ...detail });
    };
    window.addEventListener("openfic:plugin-event", localEvent);
    const initialize = () => {
      reply({
        type: "init",
        context: {
          pluginId: plugin.id,
          projectId,
          language,
          theme,
          settings: JSON.parse(configuration),
          ...JSON.parse(extraContext),
          sdkVersion: "2.0.0",
          capabilities: capabilityKey.split(","),
          slot: view.slot,
          ...(isOverlay
            ? { viewport: { width: window.innerWidth, height: window.innerHeight } }
            : {}),
        },
      });
      setReady(true);
      setFault(false);
      window.clearTimeout(timer);
    };
    if (initialized.current) initialize();
    const receive = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow || event.origin !== "null") return;
      const message = event.data;
      if (!message || message.protocol !== "openfic.plugin.v1") return;
      if (message.type === "ready") {
        initialized.current = true;
        initialize();
      } else if (
        message.type === "call" &&
        message.channel === channel &&
        typeof message.id === "string" &&
        typeof message.method === "string"
      ) {
        if (
          !message.params ||
          typeof message.params !== "object" ||
          Array.isArray(message.params) ||
          JSON.stringify(message.params).length >
            (message.method.startsWith("sdk.") || message.method.startsWith("host.")
              ? 4 * 1024 * 1024
              : 64000) ||
          inFlight >= 8
        ) {
          reply({
            type: "result",
            id: message.id,
            error: "Invalid request or too many pending requests",
          });
          return;
        }
        inFlight++;
        const operation =
          message.method === "host.ui.openOverlay" || message.method === "host.ui.closeOverlay"
            ? Promise.resolve().then(() => {
                if (
                  !isOverlay ||
                  !onOverlayRequest ||
                  !capabilityKey.split(",").includes("ui") ||
                  !capabilityKey.split(",").includes("ui.overlay")
                )
                  throw new Error(
                    "Opening overlays requires a mounted app.overlay view with ui and ui.overlay",
                  );
                onOverlayRequest(message.method.slice(5), message.params);
              })
            : message.method === "host.ui.setOverlayBounds"
              ? Promise.resolve().then(() => {
                  if (
                    !isOverlay ||
                    !capabilityKey.split(",").includes("ui.overlay") ||
                    !capabilityKey.split(",").includes("ui")
                  )
                    throw new Error(
                      "Overlay bounds require an app.overlay view with ui and ui.overlay",
                    );
                  const { x, y, width, height } = message.params;
                  if (
                    ![x, y, width, height].every(
                      (value) => typeof value === "number" && Number.isFinite(value),
                    ) ||
                    width < 0 ||
                    height < 0
                  )
                    throw new Error(
                      "Overlay bounds must contain finite coordinates and non-negative dimensions",
                    );
                  requestedBounds.current = { x, y, width, height };
                  requestedHeight.current = null;
                  return fitOverlay();
                })
              : message.method === "host.ui.resize"
                ? Promise.resolve().then(() => {
                    if (!capabilityKey.split(",").includes("ui"))
                      throw new Error("Plugin has not declared ui");
                    if (!embedded || (!isOverlay && !heightChange.current))
                      throw new Error("Resizing requires an embedded plugin view");
                    const height = message.params.height;
                    if (typeof height !== "number" || !Number.isFinite(height))
                      throw new Error("Plugin height must be a finite number");
                    requestedHeight.current = height;
                    return resizeView(height);
                  })
                : message.method.startsWith("host.")
                  ? frontendCall(
                      message.method.slice(5),
                      message.params,
                      capabilityKey.split(","),
                      navigate,
                      plugin.id,
                      onRequestClose,
                    )
                  : apiClient
                      .post(`/plugins/${plugin.id}/rpc`, {
                        method: message.method,
                        params: message.params,
                      })
                      .then(({ data }) => data.result);
        void operation
          .then((result) => {
            if (!disposed) reply({ type: "result", id: message.id, result });
          })
          .catch((error: unknown) => {
            if (!disposed) reply({ type: "result", id: message.id, error: pluginError(error) });
          })
          .finally(() => {
            inFlight--;
          });
      }
    };
    window.addEventListener("message", receive);
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      window.removeEventListener("message", receive);
      window.removeEventListener("openfic:plugin-event", localEvent);
      window.removeEventListener("resize", viewportResize);
    };
  }, [
    channel,
    language,
    plugin.id,
    configuration,
    projectId,
    theme,
    extraContext,
    view.slot,
    view.id,
    navigate,
    queryClient,
    capabilityKey,
    embedded,
    isOverlay,
    onRequestClose,
    onOverlayRequest,
  ]);
  const { data: viewUrl, error: viewError } = useQuery({
    queryKey: ["plugin-view-url", plugin.id, plugin.version, view.id, configuration],
    queryFn: async () => {
      const { data } = await apiClient.post<{ url: string }>(
        `/plugins/${plugin.id}/views/${view.id}`,
      );
      return resolveBackendUrl(data.url) ?? "";
    },
    gcTime: 0,
    refetchOnWindowFocus: false,
  });
  const isLoading = !ready && !fault && !(fullPage && viewError);
  return (
    <section
      className="plugin-view"
      data-overlay-iframe={isOverlay ? "true" : undefined}
      style={
        isOverlay
          ? {
              position: "fixed",
              left: overlayBounds.x,
              top: overlayBounds.y,
              width: overlayBounds.width,
              height: overlayBounds.height,
              pointerEvents: "auto",
            }
          : undefined
      }
      data-loading={fullPage && isLoading ? "true" : undefined}
    >
      {!embedded && !fullPage && (
        <Flex
          className="plugin-view-header"
          align="center"
          justify="between"
        >
          <h2>{view.title}</h2>
          <Button
            size="1"
            variant="soft"
            onClick={() => openSettings({ category: "plugins" })}
          >
            {t("plugins.management")}
          </Button>
        </Flex>
      )}
      {isLoading &&
        (fullPage ? (
          <div className="plugin-page-loading">
            <Spinner aria-label={t("plugins.loading")} />
          </div>
        ) : (
          <p role="status">{t("plugins.loading")}</p>
        ))}
      {fault && <p role="alert">{t("plugins.viewFailed")}</p>}
      {viewError && <p role="alert">{pluginError(viewError)}</p>}
      {viewUrl && (
        <iframe
          ref={frame}
          src={viewUrl}
          title={view.title}
          sandbox="allow-scripts"
          className={embedded ? "plugin-frame plugin-frame-embedded" : "plugin-frame"}
          onError={() => setFault(true)}
        />
      )}
    </section>
  );
}
