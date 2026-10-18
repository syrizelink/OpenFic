import { Button, Flex } from "@radix-ui/themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams, useNavigate } from "react-router";

import { apiClient, resolveBackendUrl } from "@/lib/api-client";

import {
  fetchPlugins,
  pluginError,
  PLUGINS_QUERY_KEY,
  type InstalledPlugin,
  type PluginView,
} from "./api";
import { frontendCall } from "./frontend-host";
import { PluginManager } from "./plugin-manager";

import "./plugins.css";

export function ExtensionsPage() {
  return (
    <div className="extensions-page">
      <PluginManager />
    </div>
  );
}

export function PluginPage() {
  const { pluginId, viewId } = useParams();
  const { t } = useTranslation();
  const {
    data: plugins,
    isLoading,
    error,
  } = useQuery({ queryKey: PLUGINS_QUERY_KEY, queryFn: fetchPlugins, refetchInterval: 5000 });
  const plugin = plugins?.find((entry) => entry.id === pluginId && entry.status === "enabled");
  const view = plugin?.views.find((entry) => entry.id === viewId);
  if (isLoading) return <p>{t("plugins.loading")}</p>;
  if (!plugin || !view || error)
    return (
      <div className="extensions-page">
        <p role="alert">{error ? pluginError(error) : t("plugins.unavailable")}</p>
        <Link to="/extensions">{t("plugins.management")}</Link>
      </div>
    );
  return (
    <PluginFrame
      key={`${plugin.id}:${plugin.version}:${view.id}:${JSON.stringify(plugin.configuration)}`}
      plugin={plugin}
      view={view}
    />
  );
}

export function PluginFrame({
  plugin,
  view,
  context = {},
  embedded = false,
  onHeightChange,
}: {
  plugin: InstalledPlugin;
  view: PluginView;
  context?: Record<string, unknown>;
  embedded?: boolean;
  onHeightChange?: (height: number) => void;
}) {
  const { t, i18n } = useTranslation();
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
  const [fault, setFault] = useState(false);
  const language = i18n.language;
  const projectId = context.projectId ?? routeParams.projectId ?? search.get("projectId");
  const extraContext = JSON.stringify(context);
  const capabilityKey = plugin.capabilities.join(",");
  const configuration = JSON.stringify(plugin.configuration);
  const theme =
    document.documentElement.classList.contains("dark") ||
    document.querySelector(".radix-themes")?.classList.contains("dark")
      ? "dark"
      : "light";
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
      const maximum =
        view.slot === "assistant.above-prompt"
          ? Math.min(420, Math.floor(window.innerHeight * 0.45))
          : 1600;
      const bounded = Math.max(0, Math.min(maximum, Math.ceil(height)));
      heightChange.current?.(bounded);
      return bounded;
    };
    const viewportResize = () => {
      if (requestedHeight.current !== null) resizeView(requestedHeight.current);
    };
    window.addEventListener("resize", viewportResize);
    const localEvent = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (detail.event.startsWith("editor.") && !capabilityKey.split(",").includes("editor.read"))
        return;
      if (!detail.event.startsWith("editor.") && !capabilityKey.split(",").includes("events"))
        return;
      reply({ type: "event", ...detail });
    };
    window.addEventListener("openfic:plugin-event", localEvent);
    const receive = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow || event.origin !== "null") return;
      const message = event.data;
      if (!message || message.protocol !== "openfic.plugin.v1") return;
      if (message.type === "ready") {
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
          },
        });
        setReady(true);
        setFault(false);
        window.clearTimeout(timer);
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
          message.method === "host.ui.resize"
            ? Promise.resolve().then(() => {
                if (!capabilityKey.split(",").includes("ui"))
                  throw new Error("Plugin has not declared ui");
                if (!embedded || !heightChange.current)
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
    navigate,
    queryClient,
    capabilityKey,
    embedded,
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
  return (
    <section className="plugin-view">
      {!embedded && (
        <Flex
          className="plugin-view-header"
          align="center"
          justify="between"
        >
          <h2>{view.title}</h2>
          <Button
            asChild
            size="1"
            variant="soft"
          >
            <Link to="/extensions">{t("plugins.management")}</Link>
          </Button>
        </Flex>
      )}
      {!ready && !fault && <p role="status">{t("plugins.loading")}</p>}
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
