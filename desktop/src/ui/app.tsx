import { useEffect, useRef, useState, type CSSProperties } from "react";
import { DesktopHeader } from "./components/header";
import { DesktopNotices } from "./components/desktop-notices";
import { InstanceDeletionDialog } from "./components/instance-deletion-dialog";
import { BootPage } from "./pages/boot/page";
import { DataManagementPage } from "./pages/data-management/page";
import { FrontendPage, type FrontendWebviewElement } from "./pages/frontend/page";
import { SetupPage } from "./pages/setup/page";
import i18n, { isDesktopLanguage } from "./i18n";
import type { DesktopConfig } from "../shared/config";
import type { StartupProgressEvent, UpdateState } from "../shared/ipc";

type ShellState = "booting" | "setup" | "frontend" | "data";
type Appearance = "light" | "dark";
type SetupInitialStep = "mode" | "remote" | "local-directory" | "local-success";

interface DesktopAppearancePayload {
  appearance?: Appearance;
  fontFamily?: string;
  codeFontFamily?: string;
}

interface SocketDiagnosticPayload {
  active?: boolean;
  attempt?: number;
  durationMs?: number;
  event: string;
  message?: string;
  transport?: string;
  url?: string;
}

interface ShellAppearance {
  appearance: Appearance;
  fontFamily?: string;
  codeFontFamily?: string;
}

interface WebviewIpcMessageEvent extends Event {
  channel: string;
  args: unknown[];
}

interface WebviewConsoleMessageEvent extends Event {
  level: number;
  line: number;
  message: string;
  sourceId: string;
}

interface WebviewFailLoadEvent extends Event {
  errorCode: number;
  errorDescription: string;
  validatedURL: string;
}

interface WebviewRenderProcessGoneEvent extends Event {
  details: {
    exitCode: number;
    reason: string;
  };
}

const MENU_SHORTCUTS = new Set([
  "menu-window",
  "menu-instance",
  "menu-help",
  "minimize-window",
  "toggle-maximize",
  "toggle-full-screen",
  "zoom-in",
  "zoom-out",
  "reset-zoom",
  "close-window",
  "toggle-dev-tools",
]);

const SOCKET_DIAGNOSTIC_EVENTS = new Set([
  "connect-start",
  "connect-error",
  "reconnect-attempt",
  "reconnect-failed",
  "connected",
  "disconnected",
  "connection-timeout",
]);

interface WebviewNavigationState {
  canGoBack: boolean;
  canGoForward: boolean;
}

const EMPTY_WEBVIEW_NAVIGATION: WebviewNavigationState = {
  canGoBack: false,
  canGoForward: false,
};

function getWebviewNavigationState(webview: FrontendWebviewElement): WebviewNavigationState {
  try {
    return {
      canGoBack: webview.canGoBack(),
      canGoForward: webview.canGoForward(),
    };
  } catch {
    return EMPTY_WEBVIEW_NAVIGATION;
  }
}

function isMenuShortcut(value: unknown): value is string {
  return typeof value === "string" && MENU_SHORTCUTS.has(value);
}

function isZoomFactor(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isDesktopAppearancePayload(value: unknown): value is DesktopAppearancePayload {
  if (!value || typeof value !== "object") return false;
  const candidate = value as DesktopAppearancePayload;
  return (
    (candidate.appearance === undefined || candidate.appearance === "light" || candidate.appearance === "dark") &&
    (candidate.fontFamily === undefined || typeof candidate.fontFamily === "string") &&
    (candidate.codeFontFamily === undefined || typeof candidate.codeFontFamily === "string")
  );
}

function isSocketDiagnosticPayload(value: unknown): value is SocketDiagnosticPayload {
  if (!value || typeof value !== "object") return false;
  const candidate = value as SocketDiagnosticPayload;
  return (
    SOCKET_DIAGNOSTIC_EVENTS.has(candidate.event) &&
    (candidate.active === undefined || typeof candidate.active === "boolean") &&
    (candidate.attempt === undefined || Number.isFinite(candidate.attempt)) &&
    (candidate.durationMs === undefined || Number.isFinite(candidate.durationMs)) &&
    (candidate.message === undefined || typeof candidate.message === "string") &&
    (candidate.transport === undefined || typeof candidate.transport === "string") &&
    (candidate.url === undefined || typeof candidate.url === "string")
  );
}

function writeFrontendDiagnostic(message: string): void {
  void window.openficDesktop.logFrontendDiagnostic(message).catch(() => undefined);
}

function formatSocketDiagnostic(payload: SocketDiagnosticPayload): string {
  const details = [
    `event=${payload.event}`,
    payload.url ? `url=${payload.url}` : null,
    payload.transport ? `transport=${payload.transport}` : null,
    payload.active === undefined ? null : `active=${payload.active}`,
    payload.attempt === undefined ? null : `attempt=${payload.attempt}`,
    payload.durationMs === undefined ? null : `durationMs=${payload.durationMs}`,
    payload.message ? `message=${payload.message}` : null,
  ].filter((value): value is string => value !== null);
  return `socket ${details.join(" ")}`;
}

function normalizeRemoteUrl(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, "");
  try {
    const parsed = new URL(trimmed);
    parsed.protocol = parsed.protocol.toLowerCase();
    parsed.hostname = parsed.hostname.toLowerCase();
    parsed.pathname = parsed.pathname.replace(/\/+$/, "");
    return parsed.toString().replace(/\/+$/, "");
  } catch {
    return trimmed;
  }
}

function getRemoteInstanceName(url: string, fallback: string): string {
  try {
    return new URL(url).host || fallback;
  } catch {
    return url || fallback;
  }
}

function createInstanceId(): string {
  return `instance-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function App() {
  const [error, setError] = useState<string | null>(null);
  const [shellState, setShellState] = useState<ShellState>("booting");
  const [webviewKey, setWebviewKey] = useState(0);
  const [config, setConfig] = useState<DesktopConfig | null>(null);
  const [activeInstanceId, setActiveInstanceId] = useState<string | null>(null);
  const [setupInitialStep, setSetupInitialStep] = useState<SetupInitialStep>("mode");
  const [setupInitialInstallDir, setSetupInitialInstallDir] = useState<string | null>(null);
  const [setupInitialRemoteUrl, setSetupInitialRemoteUrl] = useState<string | null>(null);
  const [frontendReadyPartition, setFrontendReadyPartition] = useState<string | null>(null);
  const [shellAppearance, setShellAppearance] = useState<ShellAppearance>({ appearance: "light" });
  const [compatibilityWarning, setCompatibilityWarning] = useState<string | null>(null);
  const [maintenanceWarning, setMaintenanceWarning] = useState<string | null>(null);
  const [updateState, setUpdateState] = useState<UpdateState>({ status: "idle" });
  const [updateDialogOpen, setUpdateDialogOpen] = useState(false);
  const [instancePanelOpen, setInstancePanelOpen] = useState(false);
  const [deletionInstanceId, setDeletionInstanceId] = useState<string | null>(null);
  const [dataManagementPrevState, setDataManagementPrevState] = useState<ShellState | null>(null);
  const [dataManagementInstanceId, setDataManagementInstanceId] = useState<string | null>(null);
  const [startupProgress, setStartupProgress] = useState<StartupProgressEvent | null>(null);
  const [frontendWebview, setFrontendWebview] = useState<FrontendWebviewElement | null>(null);
  const [webviewNavigation, setWebviewNavigation] = useState<WebviewNavigationState>(EMPTY_WEBVIEW_NAVIGATION);
  const lastAutoUpdateCheck = useRef<string | null>(null);
  const automaticallyOpenedUpdate = useRef<string | null>(null);
  const startupRequestId = useRef(0);
  const activeInstance = config?.instances.find((instance) => instance.id === activeInstanceId) ?? null;
  const deletionInstance = config?.instances.find((instance) => instance.id === deletionInstanceId) ?? null;
  const frontendPartition = activeInstanceId ? `persist:openfic-${activeInstanceId}` : "persist:openfic";
  const canCheckForUpdates = shellState === "frontend" && activeInstance !== null && updateState.status !== "unsupported";

  useEffect(() => {
    let cancelled = false;
    const dispose = window.openficDesktop.onStartupProgress((progress) => {
      if (!cancelled) setStartupProgress(progress);
    });

    const initialize = async () => {
      const requestId = ++startupRequestId.current;
      try {
        const currentProgress = await window.openficDesktop.getStartupProgress();
        if (!cancelled && requestId === startupRequestId.current) setStartupProgress(currentProgress);
        const result = await window.openficDesktop.initializeApp();
        const nextConfig = await window.openficDesktop.getConfig();
        if (cancelled || requestId !== startupRequestId.current) return;
        setConfig(nextConfig);
        setActiveInstanceId(result.activeInstanceId ?? nextConfig?.activeInstanceId ?? null);
        setError(result.message ?? null);
        setCompatibilityWarning(result.compatibilityWarning ?? null);
        const maintenanceWarning = result.maintenanceWarning ?? null;
        setMaintenanceWarning(maintenanceWarning);
        if (maintenanceWarning) {
          setShellState("booting");
          return;
        }
        setShellState(result.status === "ready" ? "frontend" : "setup");
      } catch (err) {
        if (cancelled || requestId !== startupRequestId.current) return;
        setError(err instanceof Error ? err.message : i18n.t("desktop.app.initializeFailed"));
        setShellState("setup");
      }
    };

    void initialize();

    return () => {
      cancelled = true;
      dispose();
    };
  }, []);

  useEffect(() => {
    if (!canCheckForUpdates || !activeInstanceId) return;
    const runtimeKey = `${activeInstanceId}:${webviewKey}`;
    if (lastAutoUpdateCheck.current === runtimeKey) return;
    lastAutoUpdateCheck.current = runtimeKey;
    void window.openficDesktop.checkForUpdate();
  }, [activeInstanceId, canCheckForUpdates, webviewKey]);

  useEffect(() => {
    let cancelled = false;
    void window.openficDesktop.getUpdateState().then((state) => {
      if (!cancelled) setUpdateState(state);
    });
    const dispose = window.openficDesktop.onUpdateState(setUpdateState);
    return () => {
      cancelled = true;
      dispose();
    };
  }, []);

  useEffect(() => {
    const handleShowSetup = () => {
      setError(null);
      setShellState("setup");
    };

    window.addEventListener("openfic:show-setup", handleShowSetup);
    return () => window.removeEventListener("openfic:show-setup", handleShowSetup);
  }, []);

  useEffect(() => {
    if (!frontendWebview) return;

    const handleIpcMessage = (event: Event) => {
      const { channel, args } = event as WebviewIpcMessageEvent;
      const payload = args[0];
      if (channel === "openfic:appearance" && isDesktopAppearancePayload(payload)) {
        setShellAppearance((current) => ({
          appearance: payload.appearance ?? current.appearance,
          fontFamily: payload.fontFamily ?? current.fontFamily,
          codeFontFamily: payload.codeFontFamily ?? current.codeFontFamily,
        }));
        return;
      }
      if (channel === "openfic:language" && isDesktopLanguage(payload)) {
        void i18n.changeLanguage(payload);
        return;
      }
      if (channel === "openfic:socket-diagnostic" && isSocketDiagnosticPayload(payload)) {
        writeFrontendDiagnostic(formatSocketDiagnostic(payload));
        return;
      }
      if (channel === "openfic:zoom-factor" && isZoomFactor(payload)) {
        void window.openficDesktop.saveZoomFactor(payload);
        return;
      }
      if (channel === "openfic:menu-shortcut" && isMenuShortcut(payload)) {
        window.dispatchEvent(new CustomEvent("openfic:menu-shortcut", { detail: payload }));
      }
    };

    const restoreZoomFactor = () => {
      void window.openficDesktop.getZoomFactor().then((zoomFactor) => {
        frontendWebview.send("openfic:zoom-factor", zoomFactor);
      });
    };

    frontendWebview.addEventListener("ipc-message", handleIpcMessage);
    frontendWebview.addEventListener("did-finish-load", restoreZoomFactor);
    restoreZoomFactor();
    return () => {
      frontendWebview.removeEventListener("ipc-message", handleIpcMessage);
      frontendWebview.removeEventListener("did-finish-load", restoreZoomFactor);
    };
  }, [frontendWebview]);

  useEffect(() => {
    if (!frontendWebview) {
      setWebviewNavigation(EMPTY_WEBVIEW_NAVIGATION);
      return;
    }

    const syncNavigationState = () => {
      setWebviewNavigation(getWebviewNavigationState(frontendWebview));
    };
    const navigationEvents = ["did-navigate", "did-navigate-in-page", "did-finish-load", "dom-ready"];

    for (const eventName of navigationEvents) frontendWebview.addEventListener(eventName, syncNavigationState);
    syncNavigationState();

    return () => {
      for (const eventName of navigationEvents) frontendWebview.removeEventListener(eventName, syncNavigationState);
    };
  }, [frontendWebview]);

  useEffect(() => {
    if (!frontendWebview) return;

    const handleConsoleMessage = (event: Event) => {
      const { level, line, message, sourceId } = event as WebviewConsoleMessageEvent;
      if (!/\b(socket|websocket|engine\.io)\b/i.test(message)) return;
      writeFrontendDiagnostic(`webview console level=${level} source=${sourceId}:${line} message=${message}`);
    };
    const handleFailLoad = (event: Event) => {
      const { errorCode, errorDescription, validatedURL } = event as WebviewFailLoadEvent;
      writeFrontendDiagnostic(`webview did-fail-load code=${errorCode} url=${validatedURL} error=${errorDescription}`);
    };
    const handleRenderProcessGone = (event: Event) => {
      const { details } = event as WebviewRenderProcessGoneEvent;
      writeFrontendDiagnostic(`webview render-process-gone reason=${details.reason} exitCode=${details.exitCode}`);
    };

    frontendWebview.addEventListener("console-message", handleConsoleMessage);
    frontendWebview.addEventListener("did-fail-load", handleFailLoad);
    frontendWebview.addEventListener("render-process-gone", handleRenderProcessGone);
    return () => {
      frontendWebview.removeEventListener("console-message", handleConsoleMessage);
      frontendWebview.removeEventListener("did-fail-load", handleFailLoad);
      frontendWebview.removeEventListener("render-process-gone", handleRenderProcessGone);
    };
  }, [frontendWebview]);

  useEffect(() => {
    if (!frontendWebview) return;

    const handleZoomFactor = (zoomFactor: number) => {
      frontendWebview.send("openfic:zoom-factor", zoomFactor);
    };

    return window.openficDesktop.onZoomFactorChanged(handleZoomFactor);
  }, [frontendWebview]);

  const refreshConfig = async () => {
    const nextConfig = await window.openficDesktop.getConfig();
    setConfig(nextConfig);
    setActiveInstanceId(nextConfig?.activeInstanceId ?? null);
    return nextConfig;
  };

  const showFrontend = async (result?: { compatibilityWarning?: string }, requestId?: number) => {
    const nextConfig = await refreshConfig();
    if (requestId !== undefined && requestId !== startupRequestId.current) return;
    setError(null);
    setCompatibilityWarning(result?.compatibilityWarning ?? null);
    setWebviewKey((key) => key + 1);
    setActiveInstanceId(nextConfig?.activeInstanceId ?? null);
    setShellState("frontend");
  };

  const enterFrontend = (requestId?: number) => {
    if (requestId !== undefined && requestId !== startupRequestId.current) return;
    setMaintenanceWarning(null);
    void showFrontend(undefined, requestId);
  };

  const handleAcknowledgeMaintenance = (requestId?: number) => {
    enterFrontend(requestId);
  };

  const handleShowSetup = (target: SetupInitialStep = "mode") => {
    setError(null);
    setSetupInitialStep(target);
    setSetupInitialInstallDir(null);
    setSetupInitialRemoteUrl(null);
    setShellState("setup");
  };

  const handleOpenDataManagement = () => {
    setError(null);
    setDataManagementPrevState(shellState);
    setDataManagementInstanceId(shellState === "frontend" ? activeInstanceId : null);
    setShellState("data");
  };

  const handleOpenDataManagementFor = (instanceId: string) => {
    setError(null);
    setDataManagementPrevState(shellState);
    setDataManagementInstanceId(instanceId);
    setShellState("data");
  };

  const handleCloseDataManagement = async () => {
    const prevState = dataManagementPrevState ?? "frontend";
    setDataManagementPrevState(null);
    setDataManagementInstanceId(null);
    if (prevState === "frontend" && activeInstance?.mode === "local") {
      await handleSwitchInstance(activeInstance.id);
      return;
    }
    setShellState(prevState);
  };

  const handleAddInstance = () => {
    const hasLocalInstance = config?.instances.some((instance) => instance.mode === "local") ?? false;
    handleShowSetup(hasLocalInstance ? "remote" : "mode");
  };

  const handleRequestDeleteInstance = (instanceId: string) => {
    if (!config?.instances.some((instance) => instance.id === instanceId)) return;
    setError(null);
    setInstancePanelOpen(false);
    setDeletionInstanceId(instanceId);
  };

  const handleSwitchInstance = async (instanceId: string) => {
    const requestId = ++startupRequestId.current;
    setError(null);
    setCompatibilityWarning(null);
    setMaintenanceWarning(null);
    setUpdateDialogOpen(false);
    setStartupProgress(null);
    setShellState("booting");
    try {
      const result = await window.openficDesktop.switchInstance(instanceId);
      const nextConfig = await refreshConfig();
      if (requestId !== startupRequestId.current) return;
      setActiveInstanceId(result.activeInstanceId ?? nextConfig?.activeInstanceId ?? instanceId);
      setCompatibilityWarning(result.compatibilityWarning ?? null);
      if (result.maintenanceWarning) {
        setMaintenanceWarning(result.maintenanceWarning);
        return;
      }
      setWebviewKey((key) => key + 1);
      setShellState(result.status === "ready" ? "frontend" : "setup");
    } catch (err) {
      if (requestId !== startupRequestId.current) return;
      setError(err instanceof Error ? err.message : i18n.t("desktop.app.switchInstanceFailed"));
      setShellState("setup");
    }
  };

  const handleDeleteInstance = async (instanceId: string, deleteData: boolean) => {
    const wasActive = activeInstanceId === instanceId;
    if (wasActive) {
      startupRequestId.current += 1;
      setStartupProgress(null);
      setShellState("booting");
    }
    try {
      const result = await window.openficDesktop.deleteInstance(instanceId, deleteData);
      setDeletionInstanceId(null);
      await refreshConfig();
      if (!wasActive) return;
      if (result.nextActiveInstanceId) {
        await handleSwitchInstance(result.nextActiveInstanceId);
        return;
      }
      startupRequestId.current += 1;
      setError(null);
      setCompatibilityWarning(null);
      setMaintenanceWarning(null);
      setStartupProgress(null);
      setSetupInitialStep("mode");
      setShellState("setup");
    } catch (error) {
      await refreshConfig().catch(() => null);
      if (wasActive) {
        startupRequestId.current += 1;
        setStartupProgress(null);
        setSetupInitialStep("mode");
        setShellState("setup");
      }
      throw error;
    }
  };

  const handleCancelStartup = async () => {
    startupRequestId.current += 1;
    await window.openficDesktop.cancelStartup();
    const nextConfig = await window.openficDesktop.getConfig();
    setError(null);
    setMaintenanceWarning(null);
    setConfig(nextConfig);
    setActiveInstanceId(nextConfig?.activeInstanceId ?? null);
    setStartupProgress(null);
    setSetupInitialStep("mode");
    setShellState("setup");
  };

  const handleConnectRemote = async (url: string) => {
    const requestId = ++startupRequestId.current;
    const normalizedUrl = normalizeRemoteUrl(url);
    setError(null);
    setCompatibilityWarning(null);
    setUpdateDialogOpen(false);
    setSetupInitialRemoteUrl(normalizedUrl);
    setStartupProgress(null);
    setShellState("booting");
    try {
      const previousConfig = await window.openficDesktop.getConfig();
      if (requestId !== startupRequestId.current) return;
      const existingInstance = previousConfig?.instances.find(
        (instance) => instance.mode === "remote" && instance.remoteUrl && normalizeRemoteUrl(instance.remoteUrl) === normalizedUrl,
      );
      const instance = existingInstance ?? {
        id: createInstanceId(),
        name: getRemoteInstanceName(normalizedUrl, i18n.t("desktop.app.remoteInstanceFallback")),
        mode: "remote" as const,
        remoteUrl: normalizedUrl,
        autoStartLocal: false,
        installDir: null,
        dataDir: null,
      };
      const nextConfig: DesktopConfig = {
        activeInstanceId: previousConfig?.activeInstanceId ?? null,
        instances: existingInstance
          ? previousConfig?.instances ?? [instance]
          : [...(previousConfig?.instances ?? []), instance],
      };
      await window.openficDesktop.saveConfig(nextConfig);
      if (requestId !== startupRequestId.current) return;
      const result = await window.openficDesktop.switchInstance(instance.id);
      if (requestId !== startupRequestId.current) return;
      await showFrontend(result, requestId);
    } catch (err) {
      if (requestId !== startupRequestId.current) return;
      setError(err instanceof Error ? err.message : i18n.t("desktop.app.connectRemoteFailed"));
      setSetupInitialStep("remote");
      setShellState("setup");
    }
  };

  const handleStartLocal = async (installDir: string, dataDir: string) => {
    const requestId = ++startupRequestId.current;
    setError(null);
    setCompatibilityWarning(null);
    setUpdateDialogOpen(false);
    setSetupInitialInstallDir(installDir);
    setStartupProgress(null);
    setShellState("booting");
    try {
      const maintenanceWarning = await window.openficDesktop.startLocalBackend(installDir, dataDir);
      if (requestId !== startupRequestId.current) return;
      if (maintenanceWarning) {
        setMaintenanceWarning(maintenanceWarning);
        return;
      }
      await showFrontend(undefined, requestId);
    } catch (err) {
      if (requestId !== startupRequestId.current) return;
      setError(err instanceof Error ? err.message : i18n.t("desktop.app.startLocalFailed"));
      setSetupInitialStep("local-directory");
      setShellState("setup");
    }
  };

  const handleSaveConfig = async (nextConfig: DesktopConfig) => {
    await window.openficDesktop.saveConfig(nextConfig);
    setConfig(nextConfig);
    setActiveInstanceId(nextConfig.activeInstanceId);
  };

  useEffect(() => {
    if (!canCheckForUpdates) setUpdateDialogOpen(false);
  }, [canCheckForUpdates]);

  const handleWebviewNavigation = (direction: "back" | "forward") => {
    if (!frontendWebview) return;

    try {
      if (direction === "back") {
        if (!frontendWebview.canGoBack()) return;
        frontendWebview.goBack();
        return;
      }
      if (!frontendWebview.canGoForward()) return;
      frontendWebview.goForward();
    } catch {
      setWebviewNavigation(EMPTY_WEBVIEW_NAVIGATION);
    }
  };

  useEffect(() => {
    if (updateState.status !== "available") {
      automaticallyOpenedUpdate.current = null;
      return;
    }
    if (compatibilityWarning) {
      automaticallyOpenedUpdate.current = null;
      setUpdateDialogOpen(false);
      return;
    }

    const updateKey = updateState.version ?? "available";
    if (automaticallyOpenedUpdate.current === updateKey) return;
    automaticallyOpenedUpdate.current = updateKey;
    setUpdateDialogOpen(true);
  }, [compatibilityWarning, updateState.status, updateState.version]);

  useEffect(() => {
    if (shellState !== "frontend") return;
    let cancelled = false;
    setFrontendReadyPartition(null);
    void window.openficDesktop.ensureInstanceSession(frontendPartition).then(() => {
      if (!cancelled) setFrontendReadyPartition(frontendPartition);
    });
    return () => {
      cancelled = true;
    };
  }, [frontendPartition, shellState]);

  const shellClassName = `desktop-shell radix-themes${shellAppearance.appearance === "dark" ? " dark" : ""}`;
  const shellStyle = {
    ...(shellAppearance.fontFamily
      ? {
          fontFamily: shellAppearance.fontFamily,
          "--app-font-family": shellAppearance.fontFamily,
          "--default-font-family": shellAppearance.fontFamily,
        }
      : {}),
    ...(shellAppearance.codeFontFamily ? { "--code-font-family": shellAppearance.codeFontFamily } : {}),
  } as CSSProperties;

  return (
    <main
      className={shellClassName}
      data-accent-color="gray"
      data-gray-color="gray"
      data-radius="medium"
      data-scaling="100%"
      style={shellStyle}
    >
      <DesktopHeader
        activeInstanceId={activeInstanceId}
        config={config}
        disabled={shellState === "booting"}
        canGoBack={shellState === "frontend" && webviewNavigation.canGoBack}
        canGoForward={shellState === "frontend" && webviewNavigation.canGoForward}
        onGoBack={() => handleWebviewNavigation("back")}
        onGoForward={() => handleWebviewNavigation("forward")}
        onAddInstance={handleAddInstance}
        onOpenSetup={() => handleShowSetup()}
        onOpenDataManagement={handleOpenDataManagement}
        onRequestDeleteInstance={handleRequestDeleteInstance}
        onSaveConfig={handleSaveConfig}
        onSwitchInstance={handleSwitchInstance}
        instancePanelOpen={instancePanelOpen}
        onInstancePanelOpenChange={(open) => {
          setInstancePanelOpen(open);
          if (open) setUpdateDialogOpen(false);
        }}
        canCheckForUpdates={canCheckForUpdates}
        updateState={updateState}
        onUpdateAction={() => {
          setInstancePanelOpen(false);
          if (!compatibilityWarning) setUpdateDialogOpen(true);
          if (["idle", "not-available", "error"].includes(updateState.status)) {
            void window.openficDesktop.checkForUpdate();
          }
        }}
      />
      <section className="desktop-content">
        {shellState === "booting" ? (
          <BootPage
            error={error}
            progress={startupProgress}
            maintenanceWarning={maintenanceWarning}
            onCancel={() => void handleCancelStartup()}
            onAcknowledgeMaintenance={() => handleAcknowledgeMaintenance()}
          />
        ) : null}
        {shellState === "setup" ? (
          <SetupPage
            initialError={error}
            initialInstallDir={setupInitialInstallDir}
            initialStep={setupInitialStep}
            initialRemoteUrl={setupInitialRemoteUrl}
            instances={config?.instances ?? []}
            activeInstanceId={activeInstanceId}
            onClearError={() => setError(null)}
            onConnectRemote={(url) => void handleConnectRemote(url)}
            onConnectInstance={(instanceId) => void handleSwitchInstance(instanceId)}
            onRequestDeleteInstance={handleRequestDeleteInstance}
            onOpenDataManagementFor={handleOpenDataManagementFor}
            onStartLocal={(installDir, dataDir) => void handleStartLocal(installDir, dataDir)}
          />
        ) : null}
        {shellState === "frontend" && frontendReadyPartition ? (
          <FrontendPage webviewKey={webviewKey} partition={frontendReadyPartition} webviewRef={setFrontendWebview} />
        ) : null}
        {shellState === "data" ? (
          <DataManagementPage
            instanceId={dataManagementInstanceId}
            instances={config?.instances ?? []}
            backendRunning={dataManagementPrevState === "frontend"}
            onSelectInstance={setDataManagementInstanceId}
            onClose={handleCloseDataManagement}
            onConfigChanged={() => void refreshConfig()}
          />
        ) : null}
      </section>
      <DesktopNotices
        compatibilityWarning={compatibilityWarning}
        updateDialogOpen={updateDialogOpen}
        updateState={updateState}
        onCheckForUpdate={() => void window.openficDesktop.checkForUpdate()}
        onDownloadUpdate={() => void window.openficDesktop.downloadUpdate()}
        onCancelDownload={() => void window.openficDesktop.cancelUpdateDownload()}
        onInstallUpdate={() => void window.openficDesktop.installUpdate()}
        onOpenRelease={() => void window.openficDesktop.openUpdateRelease()}
        onCloseCompatibilityWarning={() => setCompatibilityWarning(null)}
        onCloseUpdateDialog={() => setUpdateDialogOpen(false)}
      />
      <InstanceDeletionDialog
        key={deletionInstanceId ?? "closed"}
        instance={deletionInstance}
        onClose={() => setDeletionInstanceId(null)}
        onConfirm={handleDeleteInstance}
      />
    </main>
  );
}
