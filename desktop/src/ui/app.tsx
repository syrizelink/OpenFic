import { useEffect, useRef, useState, type CSSProperties } from "react";
import { DesktopHeader } from "./components/header";
import { DesktopNotices } from "./components/desktop-notices";
import { BootPage } from "./pages/boot/page";
import { FrontendPage } from "./pages/frontend/page";
import { SetupPage } from "./pages/setup/page";
import type { DesktopConfig } from "../shared/config";
import type { StartupProgressEvent, UpdateState } from "../shared/ipc";

type ShellState = "booting" | "setup" | "frontend";
type Appearance = "light" | "dark";
type SetupInitialStep = "mode" | "remote" | "local-directory" | "local-success";

interface DesktopAppearancePayload {
  appearance?: Appearance;
  fontFamily?: string;
  codeFontFamily?: string;
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

function isDesktopAppearancePayload(value: unknown): value is DesktopAppearancePayload {
  if (!value || typeof value !== "object") return false;
  const candidate = value as DesktopAppearancePayload;
  return (
    (candidate.appearance === undefined || candidate.appearance === "light" || candidate.appearance === "dark") &&
    (candidate.fontFamily === undefined || typeof candidate.fontFamily === "string") &&
    (candidate.codeFontFamily === undefined || typeof candidate.codeFontFamily === "string")
  );
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

function getRemoteInstanceName(url: string): string {
  try {
    return new URL(url).host || "Remote";
  } catch {
    return url || "Remote";
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
  const [updateState, setUpdateState] = useState<UpdateState>({ status: "idle" });
  const [updateDialogOpen, setUpdateDialogOpen] = useState(false);
  const [instancePanelOpen, setInstancePanelOpen] = useState(false);
  const [startupProgress, setStartupProgress] = useState<StartupProgressEvent | null>(null);
  const frontendWebviewRef = useRef<HTMLElement | null>(null);
  const lastAutoUpdateCheck = useRef<string | null>(null);
  const automaticallyOpenedUpdate = useRef<string | null>(null);
  const activeInstance = config?.instances.find((instance) => instance.id === activeInstanceId) ?? null;
  const frontendPartition = activeInstanceId ? `persist:openfic-${activeInstanceId}` : "persist:openfic";
  const canCheckForUpdates = shellState === "frontend" && activeInstance !== null && updateState.status !== "unsupported";

  useEffect(() => {
    let cancelled = false;
    const dispose = window.openficDesktop.onStartupProgress((progress) => {
      if (!cancelled) setStartupProgress(progress);
    });

    const initialize = async () => {
      try {
        const currentProgress = await window.openficDesktop.getStartupProgress();
        if (!cancelled) setStartupProgress(currentProgress);
        const result = await window.openficDesktop.initializeApp();
        const nextConfig = await window.openficDesktop.getConfig();
        if (cancelled) return;
        setConfig(nextConfig);
        setActiveInstanceId(result.activeInstanceId ?? nextConfig?.activeInstanceId ?? null);
        setError(result.message ?? null);
        setCompatibilityWarning(result.compatibilityWarning ?? null);
        setShellState(result.status === "ready" ? "frontend" : "setup");
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "初始化失败");
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
    const webview = frontendWebviewRef.current;
    if (!webview) return;

    const handleIpcMessage = (event: Event) => {
      const { channel, args } = event as WebviewIpcMessageEvent;
      if (channel !== "openfic:appearance") return;
      const payload = args[0];
      if (!isDesktopAppearancePayload(payload)) return;

      setShellAppearance((current) => ({
        appearance: payload.appearance ?? current.appearance,
        fontFamily: payload.fontFamily ?? current.fontFamily,
        codeFontFamily: payload.codeFontFamily ?? current.codeFontFamily,
      }));
    };

    webview.addEventListener("ipc-message", handleIpcMessage);
    return () => webview.removeEventListener("ipc-message", handleIpcMessage);
  }, [webviewKey]);

  const refreshConfig = async () => {
    const nextConfig = await window.openficDesktop.getConfig();
    setConfig(nextConfig);
    setActiveInstanceId(nextConfig?.activeInstanceId ?? null);
    return nextConfig;
  };

  const showFrontend = async (result?: { compatibilityWarning?: string }) => {
    const nextConfig = await refreshConfig();
    setError(null);
    setCompatibilityWarning(result?.compatibilityWarning ?? null);
    setWebviewKey((key) => key + 1);
    setActiveInstanceId(nextConfig?.activeInstanceId ?? null);
    setShellState("frontend");
  };

  const handleShowSetup = (target: SetupInitialStep = "mode") => {
    setError(null);
    setSetupInitialStep(target);
    setSetupInitialInstallDir(null);
    setSetupInitialRemoteUrl(null);
    setShellState("setup");
  };

  const handleAddInstance = () => {
    const hasLocalInstance = config?.instances.some((instance) => instance.mode === "local") ?? false;
    handleShowSetup(hasLocalInstance ? "remote" : "mode");
  };

  const handleSwitchInstance = async (instanceId: string) => {
    setError(null);
    setCompatibilityWarning(null);
    setUpdateDialogOpen(false);
    setStartupProgress(null);
    setShellState("booting");
    try {
      const result = await window.openficDesktop.switchInstance(instanceId);
      const nextConfig = await refreshConfig();
      setActiveInstanceId(result.activeInstanceId ?? nextConfig?.activeInstanceId ?? instanceId);
      setCompatibilityWarning(result.compatibilityWarning ?? null);
      setWebviewKey((key) => key + 1);
      setShellState(result.status === "ready" ? "frontend" : "setup");
    } catch (err) {
      setError(err instanceof Error ? err.message : "切换实例失败");
      setShellState("setup");
    }
  };

  const handleConnectRemote = async (url: string) => {
    const normalizedUrl = normalizeRemoteUrl(url);
    setError(null);
    setCompatibilityWarning(null);
    setUpdateDialogOpen(false);
    setSetupInitialRemoteUrl(normalizedUrl);
    setStartupProgress(null);
    setShellState("booting");
    try {
      const previousConfig = await window.openficDesktop.getConfig();
      const existingInstance = previousConfig?.instances.find(
        (instance) => instance.mode === "remote" && instance.remoteUrl && normalizeRemoteUrl(instance.remoteUrl) === normalizedUrl,
      );
      const instance = existingInstance ?? {
        id: createInstanceId(),
        name: getRemoteInstanceName(normalizedUrl),
        mode: "remote" as const,
        remoteUrl: normalizedUrl,
        autoStartLocal: false,
        installDir: null,
      };
      const nextConfig: DesktopConfig = {
        activeInstanceId: instance.id,
        instances: existingInstance
          ? previousConfig?.instances ?? [instance]
          : [...(previousConfig?.instances ?? []), instance],
      };
      await window.openficDesktop.saveConfig(nextConfig);
      const result = await window.openficDesktop.switchInstance(instance.id);
      await showFrontend(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法连接到该地址");
      setSetupInitialStep("remote");
      setShellState("setup");
    }
  };

  const handleStartLocal = async (installDir: string) => {
    setError(null);
    setCompatibilityWarning(null);
    setUpdateDialogOpen(false);
    setSetupInitialInstallDir(installDir);
    setStartupProgress(null);
    setShellState("booting");
    try {
      await window.openficDesktop.startLocalBackend(installDir);
      await showFrontend();
    } catch (err) {
      setError(err instanceof Error ? err.message : "启动后端失败");
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
        disabled={shellState !== "frontend"}
        onAddInstance={handleAddInstance}
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
        {shellState === "booting" ? <BootPage error={error} progress={startupProgress} /> : null}
        {shellState === "setup" ? (
          <SetupPage
            initialError={error}
            initialInstallDir={setupInitialInstallDir}
            initialStep={setupInitialStep}
            initialRemoteUrl={setupInitialRemoteUrl}
            onClearError={() => setError(null)}
            onConnectRemote={(url) => void handleConnectRemote(url)}
            onStartLocal={(installDir) => void handleStartLocal(installDir)}
          />
        ) : null}
        {shellState === "frontend" && frontendReadyPartition ? (
          <FrontendPage webviewKey={webviewKey} partition={frontendReadyPartition} webviewRef={frontendWebviewRef} />
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
    </main>
  );
}
